"""
SMS Webhook Handler — powered by Commune + Flask

Receives inbound SMS replies from workers, classifies YES/NO intent with OpenAI,
updates job_status.json, sends confirmation SMS to the worker, and notifies the
manager by email when all slots are filled or when a summary is requested.

Endpoints:
    POST /sms        — Commune SMS webhook (URL-encoded Twilio-style payload)
    POST /summary    — Trigger a manager summary email immediately
    GET  /health     — Liveness check

Usage:
    python webhook_handler.py

Expose publicly before registering with Commune:
    ngrok http 3000
"""
import json
import os
from datetime import datetime

from commune import CommuneClient
from flask import Flask, jsonify, request
from openai import OpenAI

# ── Clients ────────────────────────────────────────────────────────────────────

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MANAGER_EMAIL = os.environ["MANAGER_EMAIL"]
PORT = int(os.environ.get("PORT", 3000))
STATUS_FILE = os.path.join(os.path.dirname(__file__), "job_status.json")

# ── Flask app ──────────────────────────────────────────────────────────────────

app = Flask(__name__)

# ── ANSI colour helpers (terminal logging) ─────────────────────────────────────

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(colour: str, label: str, message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{colour}{BOLD}[{ts}] {label}{RESET}  {message}")

# ── Phone number setup ─────────────────────────────────────────────────────────

def get_phone_number_id() -> str:
    """Return the ID of the first provisioned Commune phone number."""
    numbers = commune.phone_numbers.list()
    if not numbers:
        raise ValueError("No phone numbers found. Provision one at commune.sh/dashboard.")
    return numbers[0].id


PHONE_NUMBER_ID = get_phone_number_id()

# ── Status file helpers ────────────────────────────────────────────────────────

def load_status() -> dict:
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE) as f:
        return json.load(f)


def save_status(data: dict) -> None:
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Reply classification ───────────────────────────────────────────────────────

def classify_reply(body: str) -> str:
    """
    Use OpenAI to classify a worker's SMS reply.
    Returns one of: YES, NO, MAYBE, OTHER
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"A gig worker replied to a job offer SMS. Classify their reply.\n\n"
                    f"Reply: \"{body}\"\n\n"
                    f"Return JSON with a single key 'intent'. Value must be one of:\n"
                    f"  YES    — confirmed, accepting, available\n"
                    f"  NO     — declining, not available, can't make it\n"
                    f"  MAYBE  — uncertain, might work, need more info\n"
                    f"  OTHER  — question, unrelated, unclear\n\n"
                    f"Example: {{\"intent\": \"YES\"}}"
                ),
            }
        ],
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("intent", "OTHER").upper()


# ── Confirmation SMS ───────────────────────────────────────────────────────────

CONFIRMATION_MESSAGES = {
    "YES": "Got it — you're confirmed! We'll send shift details shortly. Thanks.",
    "NO": "No problem, thanks for letting us know. We'll reach out for future shifts.",
    "MAYBE": "Thanks for your reply. Could you let us know for sure — YES or NO? We need to confirm the shift.",
    "OTHER": "Thanks for your message. If you meant to confirm the shift, reply YES. To decline, reply NO.",
}


def send_confirmation_sms(to: str, intent: str) -> None:
    """Send an appropriate confirmation SMS back to the worker."""
    body = CONFIRMATION_MESSAGES.get(intent, CONFIRMATION_MESSAGES["OTHER"])
    commune.sms.send(to=to, body=body, phone_number_id=PHONE_NUMBER_ID)
    log(GREEN, "SMS OUT", f"Confirmation -> {to}: \"{body}\"")


# ── Manager notification ───────────────────────────────────────────────────────

def get_or_create_inbox() -> str:
    """Get or create a 'dispatch' inbox for outbound manager emails."""
    for ib in commune.inboxes.list():
        if ib.local_part == "dispatch":
            return ib.id
    ib = commune.inboxes.create(local_part="dispatch")
    return ib.id


def notify_manager_job_filled(status: dict) -> None:
    """Email the manager when all required slots have been confirmed."""
    inbox_id = get_or_create_inbox()

    confirmed = [
        name for name, resp in status.get("responses", {}).items()
        if resp.get("intent") == "YES"
    ]

    body = (
        f"Job filled: {status['job']}\n\n"
        f"Date: {status['date']}\n"
        f"Location: {status['location']}\n\n"
        f"Confirmed workers ({len(confirmed)}):\n"
        + "\n".join(f"  - {name}" for name in confirmed)
        + "\n\nAll required slots are now filled."
    )

    commune.messages.send(
        to=MANAGER_EMAIL,
        subject=f"Job filled: {status['job']} — {status['date']}",
        text=body,
        inbox_id=inbox_id,
    )
    log(GREEN, "EMAIL", f"Manager notified: job filled -> {MANAGER_EMAIL}")


def send_summary_email(status: dict) -> None:
    """Generate an AI-written summary of current worker responses and email the manager."""
    if not status:
        log(YELLOW, "SUMMARY", "No job_status.json found — nothing to summarise.")
        return

    inbox_id = get_or_create_inbox()

    # Build a plain-text breakdown for OpenAI to summarise
    lines = [f"Job: {status.get('job', 'Unknown')}"]
    lines.append(f"Date: {status.get('date', '')}")
    lines.append(f"Location: {status.get('location', '')}")
    lines.append(f"Workers messaged: {len(status.get('dispatched', []))}")
    lines.append("")

    responses = status.get("responses", {})
    for name, resp in responses.items():
        intent = resp.get("intent", "PENDING")
        raw = resp.get("raw_reply", "")
        lines.append(f"{name}: {intent} (\"{raw}\")")

    # Workers who were dispatched but haven't replied yet
    dispatched_names = {w["name"] for w in status.get("dispatched", [])}
    replied_names = set(responses.keys())
    pending = dispatched_names - replied_names
    for name in pending:
        lines.append(f"{name}: NO REPLY")

    breakdown = "\n".join(lines)

    ai_response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a concise, professional summary email body for a hiring manager. "
                    f"Based on this worker response data:\n\n{breakdown}\n\n"
                    f"Include: number confirmed, number declined, number pending. "
                    f"One short paragraph. Plain text, no markdown."
                ),
            }
        ],
    )
    summary_text = ai_response.choices[0].message.content.strip()

    full_body = f"{summary_text}\n\n---\n\nFull breakdown:\n{breakdown}"

    commune.messages.send(
        to=MANAGER_EMAIL,
        subject=f"Worker dispatch summary: {status.get('job', 'Job')} — {status.get('date', '')}",
        text=full_body,
        inbox_id=inbox_id,
    )
    log(GREEN, "EMAIL", f"Summary sent to {MANAGER_EMAIL}")

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/sms", methods=["POST"])
def inbound_sms():
    """
    Commune SMS webhook endpoint.

    Payload is URL-encoded (Twilio-compatible):
        From=+14155550101&To=+14155559000&Body=YES&MessageSid=SM...
    """
    # Acknowledge immediately — Commune expects a fast 200 before we do work
    from_number = request.form.get("From", "").strip()
    body = request.form.get("Body", "").strip()

    if not from_number or not body:
        return jsonify({"ok": True})

    log(CYAN, "SMS IN", f"{from_number}: \"{body}\"")

    status = load_status()
    if not status:
        log(YELLOW, "WARN", "No job_status.json found. Run dispatcher.py first.")
        return jsonify({"ok": True})

    # Find which dispatched worker this reply came from
    dispatched = status.get("dispatched", [])
    worker = next((w for w in dispatched if w["phone"] == from_number), None)

    if not worker:
        log(YELLOW, "SKIP", f"Unknown number {from_number} — not in dispatched list.")
        return jsonify({"ok": True})

    worker_name = worker["name"]

    # Classify the reply intent
    intent = classify_reply(body)
    log(
        GREEN if intent == "YES" else RED if intent == "NO" else YELLOW,
        "CLASSIFY",
        f"{worker_name}: intent={intent} (raw: \"{body}\")",
    )

    # Update status
    status.setdefault("responses", {})[worker_name] = {
        "phone": from_number,
        "raw_reply": body,
        "intent": intent,
        "replied_at": datetime.utcnow().isoformat() + "Z",
    }
    save_status(status)

    # Send confirmation SMS back to worker
    send_confirmation_sms(from_number, intent)

    # Check if all required slots are now filled
    slots_required = status.get("slots_required", 3)
    confirmed_count = sum(
        1 for r in status["responses"].values() if r.get("intent") == "YES"
    )

    if confirmed_count >= slots_required:
        log(GREEN, "FILLED", f"{confirmed_count}/{slots_required} slots confirmed — notifying manager.")
        notify_manager_job_filled(status)

    return jsonify({"ok": True})


@app.route("/summary", methods=["POST"])
def trigger_summary():
    """
    Manually trigger a manager summary email.
    Can be called by a cron job or manually during / after the dispatch window.

    Example:
        curl -X POST http://localhost:3000/summary
    """
    status = load_status()
    send_summary_email(status)
    return jsonify({"ok": True, "message": f"Summary emailed to {MANAGER_EMAIL}"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{BOLD}Worker dispatch webhook handler{RESET}")
    print(f"  POST /sms     — inbound worker replies")
    print(f"  POST /summary — email manager summary")
    print(f"  GET  /health  — liveness check")
    print(f"\n  Manager email: {MANAGER_EMAIL}")
    print(f"  Listening on port {PORT}\n")
    app.run(host="0.0.0.0", port=PORT)
