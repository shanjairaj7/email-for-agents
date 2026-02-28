"""
Incident Alert Agent
Receives alerts via POST /alert, sends SMS + email to on-call, escalates if no ACK.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from commune import CommuneClient
from flask import Flask, jsonify, request
from openai import OpenAI

load_dotenv()

# Validate required environment variables at startup
_REQUIRED_ENV = [
    "COMMUNE_API_KEY", "OPENAI_API_KEY", "COMMUNE_INBOX_ID",
    "COMMUNE_PHONE_NUMBER_ID", "ONCALL_EMAIL", "ONCALL_PHONE",
    "SECONDARY_EMAIL", "SECONDARY_PHONE", "MANAGER_EMAIL",
]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise SystemExit(f"Missing required environment variable: {_var}\n"
                         f"Copy .env.example to .env and fill in your values.")

app = Flask(__name__)

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

INBOX_ID = os.environ["COMMUNE_INBOX_ID"]
PHONE_NUMBER_ID = os.environ["COMMUNE_PHONE_NUMBER_ID"]
ONCALL_EMAIL = os.environ["ONCALL_EMAIL"]
ONCALL_PHONE = os.environ["ONCALL_PHONE"]
SECONDARY_EMAIL = os.environ["SECONDARY_EMAIL"]
SECONDARY_PHONE = os.environ["SECONDARY_PHONE"]
MANAGER_EMAIL = os.environ["MANAGER_EMAIL"]
ESCALATION_MINUTES = int(os.environ.get("ESCALATION_MINUTES", "10"))

STATE_FILE = Path("alert_state.json")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_acknowledged(alert_id: str) -> None:
    state = load_state()
    if alert_id in state:
        state[alert_id]["acknowledged"] = True
        state[alert_id]["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state)


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

def assess_and_summarise(title: str, severity: str, details: str) -> dict:
    """Use OpenAI to assess severity and write a clear, actionable summary."""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an incident response assistant. Given an incident report, "
                    "return a JSON object with two fields:\n"
                    "- sms_message: a short (<160 char) SMS text conveying urgency and what's broken\n"
                    "- email_body: a clear 3-5 sentence summary for the on-call engineer, "
                    "including what's broken, likely impact, and suggested first steps"
                ),
            },
            {
                "role": "user",
                "content": f"Title: {title}\nSeverity: {severity}\nDetails: {details}",
            },
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Notification senders
# ---------------------------------------------------------------------------

def send_sms_alert(phone: str, message: str) -> None:
    commune.sms.send(
        to=phone,
        body=message,
        phone_number_id=PHONE_NUMBER_ID,
    )


def send_email_alert(
    to: str,
    subject: str,
    body: str,
    runbook_url: str | None = None,
    cc: list[str] | None = None,
) -> str:
    """Send alert email and return thread_id."""
    full_body = body
    if runbook_url:
        full_body += f"\n\nRunbook: {runbook_url}"
    full_body += (
        "\n\n---\nReply with ACK, acknowledged, or resolved to stop escalation."
    )

    result = commune.messages.send(
        to=to,
        subject=subject,
        text=full_body,
        inbox_id=INBOX_ID,
    )
    return result.thread_id


# ---------------------------------------------------------------------------
# Escalation watcher
# ---------------------------------------------------------------------------

def escalation_watcher(alert_id: str, thread_id: str, title: str, details: str) -> None:
    """Background thread: escalate after ESCALATION_MINUTES if no ACK."""
    deadline = time.time() + ESCALATION_MINUTES * 60
    while time.time() < deadline:
        time.sleep(30)
        state = load_state()
        if state.get(alert_id, {}).get("acknowledged"):
            print(f"[{alert_id}] Acknowledged — stopping escalation.")
            return

    # Still no ACK — escalate
    state = load_state()
    if state.get(alert_id, {}).get("acknowledged"):
        return  # Acknowledged right at the boundary — skip

    print(f"[{alert_id}] No acknowledgment after {ESCALATION_MINUTES}min — escalating.")

    escalation_sms = (
        f"ESCALATION: {title} — primary on-call has not responded. "
        f"Please respond immediately."
    )
    send_sms_alert(SECONDARY_PHONE, escalation_sms)

    escalation_body = (
        f"ESCALATION: The following incident has not been acknowledged by the primary "
        f"on-call engineer after {ESCALATION_MINUTES} minutes.\n\n"
        f"Incident: {title}\n\nDetails:\n{details}"
    )
    commune.messages.send(
        to=SECONDARY_EMAIL,
        subject=f"ESCALATION: {title}",
        text=escalation_body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    # CC manager
    commune.messages.send(
        to=MANAGER_EMAIL,
        subject=f"[ESCALATED] {title}",
        text=f"FYI — incident escalated to secondary on-call.\n\n{escalation_body}",
        inbox_id=INBOX_ID,
    )

    state[alert_id]["escalated"] = True
    state[alert_id]["escalated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/alert", methods=["POST"])
def receive_alert():
    data = request.get_json(force=True)
    title = data.get("title", "Untitled incident")
    severity = data.get("severity", "unknown").lower()
    details = data.get("details", "")
    runbook_url = data.get("runbook_url")

    alert_id = f"alert_{int(time.time() * 1000)}"

    # AI assessment
    ai = assess_and_summarise(title, severity, details)
    sms_message = ai.get("sms_message", f"ALERT [{severity.upper()}]: {title}")
    email_body = ai.get("email_body", details)

    # Send SMS for high/critical severity
    if severity in ("high", "critical"):
        send_sms_alert(ONCALL_PHONE, sms_message)

    # Always send email
    subject = f"[{severity.upper()}] {title}"
    thread_id = send_email_alert(
        to=ONCALL_EMAIL,
        subject=subject,
        body=email_body,
        runbook_url=runbook_url,
    )

    # Record state
    state = load_state()
    state[alert_id] = {
        "alert_id": alert_id,
        "title": title,
        "severity": severity,
        "thread_id": thread_id,
        "acknowledged": False,
        "escalated": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)

    # Start escalation watcher in background
    t = threading.Thread(
        target=escalation_watcher,
        args=(alert_id, thread_id, title, details),
        daemon=True,
    )
    t.start()

    return jsonify({"alert_id": alert_id, "thread_id": thread_id, "status": "sent"})


@app.route("/acknowledge", methods=["POST"])
def acknowledge():
    """Manually mark an alert as acknowledged."""
    data = request.get_json(force=True)
    alert_id = data.get("alert_id")
    if not alert_id:
        return jsonify({"error": "alert_id required"}), 400
    mark_acknowledged(alert_id)
    return jsonify({"status": "acknowledged"})


@app.route("/status", methods=["GET"])
def status():
    return jsonify(load_state())


if __name__ == "__main__":
    print("Incident alert agent running on http://localhost:5000")
    app.run(port=5000, debug=False)
