"""
Two-way SMS agent (minimal Flask implementation).

Receives inbound SMS via Commune webhook, loads full conversation history,
generates a reply via GPT-4o-mini, and sends it back.

This is the leanest starting point for a custom SMS agent. It deliberately
has no extra features so it's easy to read and modify.

Usage:
  python agent.py

Environment:
  COMMUNE_API_KEY   — your Commune API key
  OPENAI_API_KEY    — your OpenAI API key
  PHONE_NUMBER_ID   — the Commune phone number ID (pn_...)
  SYSTEM_PROMPT     — optional: override the default system prompt

Expose with ngrok for local testing:
  ngrok http 8000
  # Set https://<id>.ngrok.io/webhook/sms as your Commune webhook URL
"""

import os
import sys
from flask import Flask, request, jsonify
from commune import CommuneClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Validate required environment variables at startup so failure is obvious.
required_vars = ["COMMUNE_API_KEY", "OPENAI_API_KEY", "PHONE_NUMBER_ID"]
for var in required_vars:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]

# Allow the system prompt to be overridden via env without changing code.
# This makes it easy to deploy different "personas" from the same codebase.
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant communicating via SMS. "
    "Keep replies under 160 characters and use plain text — no markdown or bullet points."
)
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

app = Flask(__name__)


@app.route("/webhook/sms", methods=["POST"])
def handle_inbound_sms():
    """
    Process an inbound SMS from Commune and send an AI-generated reply.

    Commune sends a JSON payload with:
      from_number  — E.164 number of the sender
      to_number    — our Commune phone number
      body         — text content of the incoming message
      thread_id    — stable conversation thread identifier
    """

    # TODO: Add HMAC signature verification here for production deployments.
    # Commune sends a 'commune-signature' header. Compare it against your
    # webhook secret (COMMUNE_WEBHOOK_SECRET env var) using hmac.compare_digest().

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    from_number: str = data.get("from_number", "")
    body: str = data.get("body", "").strip()

    # Guard against malformed payloads before doing any API calls.
    if not from_number:
        return jsonify({"error": "Missing from_number in payload"}), 400

    # Empty body is valid (e.g. MMS image with no caption). Nothing to reply to.
    if not body:
        return jsonify({"status": "ok", "note": "empty body — no reply sent"})

    # Fetch conversation history so the LLM has context for multi-turn dialogue.
    # An empty history is fine — the agent still works for first-time senders.
    try:
        history = commune.sms.thread(
            remote_number=from_number,
            phone_number_id=PHONE_NUMBER_ID,
        )
    except Exception as e:
        print(f"[warn] Could not fetch thread for {from_number}: {e}")
        history = []

    # Build the OpenAI messages array. Map Commune directions to OpenAI roles:
    #   inbound  → "user"       (messages they sent to us)
    #   outbound → "assistant"  (messages we sent to them)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:  # window of 10 keeps token usage predictable
        role = "user" if msg.direction == "inbound" else "assistant"
        content = msg.content or ""
        if content:
            messages.append({"role": role, "content": content})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        reply = response.choices[0].message.content or "Sorry, I couldn't generate a reply."
    except Exception as e:
        print(f"[error] OpenAI call failed: {e}")
        reply = "Something went wrong. Please try again in a moment."

    try:
        commune.sms.send(
            to=from_number,
            body=reply,
            phone_number_id=PHONE_NUMBER_ID,
        )
    except Exception as e:
        print(f"[error] Failed to send reply to {from_number}: {e}")
        return jsonify({"error": "Failed to send reply"}), 500

    print(f"[sms] from={from_number} body='{body[:50]}' reply='{reply[:50]}'")
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"Two-way SMS agent starting on port 8000")
    print(f"Webhook URL: POST /webhook/sms")
    print(f"Phone number ID: {PHONE_NUMBER_ID}")
    try:
        app.run(port=8000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down.")
        sys.exit(0)
