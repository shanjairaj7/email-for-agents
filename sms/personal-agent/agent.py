"""
Personal AI assistant with a real phone number.

Two modes run simultaneously in one process:
  - Proactive: background thread sends a morning summary at 9am every day
  - Reactive: Flask webhook receives your texts and replies via GPT-4o-mini

Only responds to texts from MY_PHONE_NUMBER — all other senders are ignored.

Usage:
  python agent.py
"""

import os
import sys
import time
import threading
import datetime
import zoneinfo
from flask import Flask, request, jsonify
from commune import CommuneClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Validate required environment variables at startup.
required_vars = [
    "COMMUNE_API_KEY",
    "OPENAI_API_KEY",
    "PHONE_NUMBER_ID",
    "MY_PHONE_NUMBER",
]
for var in required_vars:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MY_PHONE = os.environ["MY_PHONE_NUMBER"]       # your personal cell number (E.164)
PHONE_ID = os.environ["PHONE_NUMBER_ID"]       # Commune phone number used for this agent
OWNER_NAME = os.environ.get("OWNER_NAME", "there")
TIMEZONE = os.environ.get("TIMEZONE", "US/Eastern")

# Validate the timezone string early so the error is obvious at startup.
try:
    _TZ = zoneinfo.ZoneInfo(TIMEZONE)
except zoneinfo.ZoneInfoNotFoundError:
    raise SystemExit(f"Invalid TIMEZONE: '{TIMEZONE}'. Use IANA names like 'US/Eastern' or 'America/New_York'.")

SYSTEM_PROMPT = (
    f"You are {OWNER_NAME}'s personal AI assistant, reachable via SMS. "
    f"You're helpful, concise, and friendly. "
    f"Keep SMS responses under 160 characters whenever possible — use plain text only, no markdown. "
    f"You have access to conversation history, so you can reference earlier messages."
)


# ---------------------------------------------------------------------------
# Proactive: morning summary
# ---------------------------------------------------------------------------

def send_morning_summary() -> None:
    """
    Background thread: send a morning summary at 9am every day.

    In a real deployment you'd pull from a calendar API, todo list, or database
    here. This example sends a placeholder that you can customize.
    """
    summary_sent_today: str | None = None  # track which date we last sent

    while True:
        # Use the owner's configured timezone so 9am fires at the right local time,
        # not at 9am UTC (which would be wrong on any cloud server).
        now = datetime.datetime.now(tz=_TZ)
        today = now.strftime("%Y-%m-%d")

        # Send at 9:00am in the owner's timezone, once per day
        if now.hour == 9 and now.minute == 0 and summary_sent_today != today:
            message = (
                f"Good morning {OWNER_NAME}! "
                f"Today is {now.strftime('%A %B %-d')}. "
                f"Reply with anything — I'm here."
            )
            # In production: pull from calendar/todos here and include in message
            try:
                commune.sms.send(
                    to=MY_PHONE,
                    body=message,
                    phone_number_id=PHONE_ID,
                )
                print(f"[morning] Summary sent to {MY_PHONE}")
                summary_sent_today = today
            except Exception as e:
                print(f"[warn] Could not send morning summary: {e}")

            # Sleep 61 seconds so we don't re-trigger in the same minute
            time.sleep(61)
        else:
            # Check every 30 seconds — low overhead, fast enough response
            time.sleep(30)


# ---------------------------------------------------------------------------
# Reactive: webhook server
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/webhook/sms", methods=["POST"])
def handle_text():
    """
    Receive an inbound SMS from Commune and reply via GPT-4o-mini.

    Only processes messages from MY_PHONE_NUMBER — this keeps the agent
    private so only you can use it.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    from_number: str = data.get("from_number", "")
    body: str = data.get("body", "").strip()

    # Security: only respond to texts from the owner's number.
    # Texts from anyone else are silently ignored, not replied to.
    if from_number != MY_PHONE:
        print(f"[ignored] Text from {from_number} — not the owner")
        return jsonify({"status": "ignored"})

    if not body:
        return jsonify({"status": "ok", "note": "empty body"})

    # Fetch the full conversation history so the LLM can reference earlier messages.
    # Using a window of 20 messages gives good context without ballooning token usage.
    try:
        history = commune.sms.thread(
            remote_number=MY_PHONE,
            phone_number_id=PHONE_ID,
        )
    except Exception as e:
        print(f"[warn] Could not fetch thread: {e}")
        history = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-20:]:
        role = "user" if msg.direction == "inbound" else "assistant"
        content = msg.content or ""
        if content:
            messages.append({"role": role, "content": content})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        reply = response.choices[0].message.content or "I couldn't generate a reply — try again."
    except Exception as e:
        print(f"[error] OpenAI call failed: {e}")
        reply = "Something went wrong on my end. Try again in a moment."

    try:
        commune.sms.send(
            to=MY_PHONE,
            body=reply,
            phone_number_id=PHONE_ID,
        )
    except Exception as e:
        print(f"[error] Failed to send reply: {e}")
        return jsonify({"error": "Failed to send reply"}), 500

    print(f"[reply] '{body[:50]}' → '{reply[:50]}'")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Personal agent starting.")
    print(f"Owner: {OWNER_NAME} ({MY_PHONE})")
    print(f"Phone number ID: {PHONE_ID}")
    print(f"Morning summaries: 9am daily")

    # Start the proactive morning summary thread.
    # daemon=True means it exits automatically when the main process exits.
    morning_thread = threading.Thread(target=send_morning_summary, daemon=True)
    morning_thread.start()

    print(f"Webhook server on port 8000. Text {MY_PHONE} to chat.")
    try:
        app.run(port=8000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down.")
        sys.exit(0)
