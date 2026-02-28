"""
SMS Alert Agent — powered by Commune

Monitors an email inbox and sends SMS alerts for high-urgency emails.
Shows Commune's unified email + SMS API in one agent.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    export ALERT_PHONE=+14155551234        # your phone number for alerts
    python agent.py
"""
import os, json, time
from commune import CommuneClient
from openai import OpenAI

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
ALERT_PHONE = os.environ["ALERT_PHONE"]

# ── Inbox setup ────────────────────────────────────────────────────────────

def get_inbox(name="monitoring"):
    """Get an existing inbox by local part, or create one."""
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address

INBOX_ID, INBOX_ADDRESS = get_inbox()

# ── SMS phone number setup ─────────────────────────────────────────────────

def get_phone_number():
    """Get the first provisioned phone number."""
    numbers = commune.phone_numbers.list()
    if not numbers:
        raise ValueError(
            "No phone numbers found. Provision one at commune.email/dashboard."
        )
    return numbers[0].id, numbers[0].number

PHONE_ID, PHONE_NUMBER = get_phone_number()

# ── Email classification ───────────────────────────────────────────────────

def classify_urgency(subject: str, content: str) -> dict:
    """Use LLM to classify email urgency."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": f"""Classify this email urgency.

Subject: {subject}
Content: {content[:500]}

Return JSON: {{"urgency": "low|medium|high", "reason": "brief reason", "summary": "one line summary"}}"""
        }]
    )
    return json.loads(response.choices[0].message.content)

# ── SMS alert ──────────────────────────────────────────────────────────────

def send_sms_alert(classification: dict, sender: str, subject: str):
    """Send SMS alert for high-urgency email."""
    # SMS messages are capped at 160 characters for single-segment delivery
    message = f"Urgent email from {sender}\n{subject}\n{classification['reason']}"
    result = commune.sms.send(
        to=ALERT_PHONE,
        body=message[:160],
        phone_number_id=PHONE_ID,
    )
    print(f"  SMS alert sent to {ALERT_PHONE}: {result.message_id}")

# ── Main loop ──────────────────────────────────────────────────────────────

def main():
    handled = set()
    print(f"Alert agent monitoring: {INBOX_ADDRESS}")
    print(f"SMS alerts -> {ALERT_PHONE}\n")

    while True:
        result = commune.threads.list(inbox_id=INBOX_ID, limit=10)

        for thread in result.data:
            # Skip threads we've already processed or that were outbound
            if thread.thread_id in handled or thread.last_direction != "inbound":
                handled.add(thread.thread_id)
                continue

            # Load the full message list and find the last inbound message
            messages = commune.threads.messages(thread.thread_id)
            last = next(
                (m for m in reversed(messages) if m.direction == "inbound"),
                None,
            )
            if not last:
                continue

            sender = next(
                (p.identity for p in last.participants if p.role == "sender"),
                "unknown",
            )
            print(f"\nEmail from {sender}: {thread.subject}")

            # Classify urgency with LLM
            classification = classify_urgency(
                thread.subject or "",
                last.content or "",
            )
            print(f"  Urgency: {classification['urgency']} — {classification['reason']}")

            # Only alert on high-urgency emails
            if classification["urgency"] == "high":
                send_sms_alert(classification, sender, thread.subject or "(no subject)")

            handled.add(thread.thread_id)

        time.sleep(30)

if __name__ == "__main__":
    main()
