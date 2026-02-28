"""
AI agent with its own phone number.

Runs a Flask webhook server. When someone texts the agent's Commune phone number,
this server receives the inbound SMS, fetches conversation history, generates a
GPT-4o-mini reply, and sends it back via SMS.

Usage:
  python agent.py

Requirements:
  - COMMUNE_API_KEY: your Commune API key
  - OPENAI_API_KEY: your OpenAI API key
  - PHONE_NUMBER_ID: the Commune phone number ID (pn_...) to use for sending
"""

import os
import sys
from flask import Flask, request, jsonify
from commune import CommuneClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Validate all required environment variables at startup.
# Catching these early means a clear error message instead of a confusing 500 later.
required_vars = ["COMMUNE_API_KEY", "OPENAI_API_KEY", "PHONE_NUMBER_ID"]
for var in required_vars:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]

# The system prompt establishes the agent's persona and SMS-specific constraints.
# SMS has no markdown support and carriers charge per 160-char segment, so brevity matters.
SYSTEM_PROMPT = """You are a helpful AI assistant reachable via SMS.
Keep your replies concise — under 160 characters whenever possible.
Use plain text only — no markdown, bullet points, or formatting."""

app = Flask(__name__)


@app.route("/webhook/sms", methods=["POST"])
def handle_inbound_sms():
    """
    Receive an inbound SMS from Commune, generate a reply, send it back.

    Commune POST body (JSON):
      from_number  — E.164 number of the sender
      to_number    — our Commune phone number
      body         — the text content of the incoming SMS
      thread_id    — stable conversation thread identifier
      message_sid  — carrier message ID
    """

    # TODO: Add HMAC signature verification here before going to production.
    # Commune sends a 'commune-signature' header. Verify it against your webhook secret
    # using the same pattern as typescript/webhook-handler/verifyCommuneWebhook.
    # Example: hmac.compare_digest(expected_sig, request.headers.get("commune-signature", ""))

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    from_number: str = data.get("from_number", "")
    body: str = data.get("body", "").strip()

    if not from_number:
        return jsonify({"error": "Missing from_number"}), 400

    # Empty body is valid (e.g. MMS with no caption). Acknowledge and return early.
    if not body:
        return jsonify({"status": "ok", "note": "empty body — no reply sent"})

    try:
        # Fetch the full conversation history so the LLM has context for multi-turn dialogue.
        # thread() returns messages ordered oldest-first.
        history = commune.sms.thread(
            remote_number=from_number,
            phone_number_id=PHONE_NUMBER_ID,
        )
    except Exception as e:
        print(f"[warn] Could not fetch thread for {from_number}: {e}")
        history = []

    # Build the messages array for OpenAI. Map Commune's direction field to OpenAI roles:
    #   inbound  → "user"   (messages they sent to us)
    #   outbound → "assistant" (messages we sent to them)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:  # keep the last 10 messages to limit token usage
        role = "user" if msg.direction == "inbound" else "assistant"
        content = msg.content or ""
        if content:  # skip empty messages (e.g. MMS-only)
            messages.append({"role": role, "content": content})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        reply = response.choices[0].message.content or "Sorry, I couldn't generate a reply."
    except Exception as e:
        print(f"[error] OpenAI call failed: {e}")
        reply = "Sorry, something went wrong. Please try again in a moment."

    try:
        commune.sms.send(
            to=from_number,
            body=reply,
            phone_number_id=PHONE_NUMBER_ID,
        )
    except Exception as e:
        print(f"[error] Failed to send reply to {from_number}: {e}")
        return jsonify({"error": "Failed to send reply"}), 500

    print(f"[sms] {from_number} → '{body[:60]}...' | reply='{reply[:60]}...'")
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"Agent starting on port 8000. Webhook: POST /webhook/sms")
    print(f"Phone number ID: {PHONE_NUMBER_ID}")
    try:
        app.run(port=8000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down.")
        sys.exit(0)
