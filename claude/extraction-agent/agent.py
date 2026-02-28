"""
Claude Structured Extraction Agent — powered by Commune

Commune extracts structured JSON from every inbound email automatically,
before your agent even sees it. This agent configures the extraction schema,
then receives webhook events with pre-parsed fields (intent, urgency, etc.)
that Claude uses to route and respond — with no extra parsing LLM call needed.

Install:
    pip install anthropic commune-mail flask requests

Usage:
    export COMMUNE_API_KEY=comm_...
    export ANTHROPIC_API_KEY=sk-ant-...
    python agent.py
"""
import os, json, time
from dotenv import load_dotenv
import requests
import anthropic
from commune import CommuneClient
from flask import Flask, request, jsonify

load_dotenv()

# Validate required environment variables at startup
_REQUIRED_ENV = ["COMMUNE_API_KEY", "ANTHROPIC_API_KEY"]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise SystemExit(f"Missing required environment variable: {_var}\n"
                         f"Copy .env.example to .env and fill in your values.")

commune_client = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

COMMUNE_API_BASE = "https://api.commune.sh/v1"
COMMUNE_API_KEY = os.environ["COMMUNE_API_KEY"]

app = Flask(__name__)

# ── Inbox setup ───────────────────────────────────────────────────────────────

def get_inbox(name: str = "support"):
    for ib in commune_client.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune_client.inboxes.create(local_part=name)
    return ib.id, ib.address

INBOX_ID, INBOX_ADDRESS = get_inbox()

# ── Configure extraction schema on the inbox ──────────────────────────────────
#
# Commune applies this schema to every inbound email automatically.
# The extracted fields are available in the webhook payload under
# `extracted_data` before your agent processes the message.
#
# The Python SDK may not expose this endpoint directly; we call it via REST.

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["question", "billing", "bug_report", "feature_request", "cancellation"],
            "description": "The primary intent of the email"
        },
        "urgency": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How urgently the sender needs a response"
        },
        "order_number": {
            "type": ["string", "null"],
            "description": "Order or invoice number mentioned in the email, or null"
        },
        "sentiment": {
            "type": "string",
            "enum": ["positive", "neutral", "negative"],
            "description": "Overall sentiment of the email"
        }
    },
    "required": ["intent", "urgency", "sentiment"]
}

def configure_extraction():
    """Register the extraction schema with Commune for this inbox."""
    resp = requests.patch(
        f"{COMMUNE_API_BASE}/inboxes/{INBOX_ID}",
        headers={
            "Authorization": f"Bearer {COMMUNE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"extraction_schema": EXTRACTION_SCHEMA},
    )
    if resp.ok:
        print("Extraction schema configured on inbox.")
    else:
        print(f"Warning: could not configure extraction schema — {resp.status_code} {resp.text}")

# ── Routing logic ─────────────────────────────────────────────────────────────

# Maps intent to a canned escalation note Claude can reference.
ROUTING_NOTES = {
    "billing": "This is a billing issue. If it involves a refund or charge dispute, mention our 30-day refund policy.",
    "bug_report": "This is a bug report. Acknowledge the issue, ask for steps to reproduce if not provided, and mention the engineering team will investigate.",
    "cancellation": "The customer wants to cancel. Acknowledge their request, confirm it will be processed, and offer a brief pause option if relevant.",
    "feature_request": "This is a feature request. Thank them sincerely and let them know you will pass it to the product team.",
    "question": "This is a general question. Answer helpfully and concisely.",
}

def get_routing_note(extracted_data: dict) -> str:
    intent = extracted_data.get("intent", "question")
    urgency = extracted_data.get("urgency", "medium")
    note = ROUTING_NOTES.get(intent, ROUTING_NOTES["question"])
    if urgency == "high":
        note += " Urgency is HIGH — prioritise a warm, prompt response."
    return note

# ── Claude reply generation ───────────────────────────────────────────────────

def generate_reply(
    thread_id: str,
    messages: list[dict],
    extracted_data: dict,
) -> str:
    """Ask Claude to draft a reply. Extracted data is injected directly into the prompt."""
    routing_note = get_routing_note(extracted_data)
    conversation = "\n\n".join(
        f"[{m['direction'].upper()}] {m['content']}" for m in messages
    )

    response = anthropic_client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=f"""You are a customer support agent for a software company. Your inbox: {INBOX_ADDRESS}

Routing guidance (pre-extracted from the email — no need to re-parse):
- Intent: {extracted_data.get('intent', 'unknown')}
- Urgency: {extracted_data.get('urgency', 'medium')}
- Sentiment: {extracted_data.get('sentiment', 'neutral')}
- Order number: {extracted_data.get('order_number') or 'none mentioned'}

{routing_note}

Write a concise, professional reply. Sign off as "Support Team".""",
        messages=[
            {
                "role": "user",
                "content": f"Here is the email thread:\n\n{conversation}\n\nWrite a reply.",
            }
        ],
    )

    return response.content[0].text

# ── Tool definitions for Claude (optional enrichment tools) ──────────────────
#
# Because Commune already extracted the structured data, Claude does not need
# to call tools to figure out intent or urgency. These tools are available for
# cases where Claude wants to look up history or send the reply.

TOOLS = [
    {
        "name": "get_thread_messages",
        "description": "Fetch the full message history for a thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"}
            },
            "required": ["thread_id"]
        }
    },
    {
        "name": "search_past_emails",
        "description": "Semantic search across past email threads for similar issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "send_reply",
        "description": "Send a reply in the email thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "thread_id": {"type": "string"}
            },
            "required": ["to", "subject", "body", "thread_id"]
        }
    }
]

def execute_tool(name: str, input_data: dict) -> str:
    if name == "get_thread_messages":
        msgs = commune_client.threads.messages(input_data["thread_id"])
        return json.dumps([{
            "direction": m.direction,
            "sender": next((p.identity for p in m.participants if p.role == "sender"), "unknown"),
            "content": m.content,
        } for m in msgs])

    elif name == "search_past_emails":
        results = commune_client.search.threads(query=input_data["query"], inbox_id=INBOX_ID, limit=3)
        return json.dumps([{"thread_id": r.thread_id, "subject": r.subject} for r in results])

    elif name == "send_reply":
        result = commune_client.messages.send(
            to=input_data["to"], subject=input_data["subject"],
            text=input_data["body"], inbox_id=INBOX_ID,
            thread_id=input_data["thread_id"]
        )
        return json.dumps({"status": "sent", "message_id": getattr(result, "message_id", "ok")})

    return json.dumps({"error": f"Unknown tool: {name}"})

# ── Webhook handler ───────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Commune fires a POST to this endpoint when a new email arrives.

    Payload shape:
    {
      "event": "message.received",
      "thread_id": "thr_...",
      "message": { ... },
      "extracted_data": {
        "intent": "billing",
        "urgency": "high",
        "order_number": "ORD-1234",
        "sentiment": "negative"
      }
    }

    Because Commune already extracted the structured fields, we skip any
    classification step and go straight to routing + reply generation.
    """
    payload = request.get_json(force=True)

    if payload.get("event") != "message.received":
        return jsonify({"ok": True})

    thread_id = payload["thread_id"]
    extracted_data = payload.get("extracted_data", {})

    print(f"\nInbound email | thread: {thread_id}")
    print(f"  intent={extracted_data.get('intent')} urgency={extracted_data.get('urgency')} sentiment={extracted_data.get('sentiment')}")

    # Fetch the thread so we have sender info and full message history
    messages_raw = commune_client.threads.messages(thread_id)
    messages = [{
        "direction": m.direction,
        "sender": next((p.identity for p in m.participants if p.role == "sender"), "unknown"),
        "content": m.content,
    } for m in messages_raw]

    # Identify the original sender to reply to
    sender = next((m["sender"] for m in messages if m["direction"] == "inbound"), None)
    if not sender:
        print("  Could not identify sender — skipping.")
        return jsonify({"ok": True})

    # Fetch the thread subject
    thread_list = commune_client.threads.list(inbox_id=INBOX_ID, limit=50)
    subject = next(
        (t.subject for t in thread_list.data if t.thread_id == thread_id),
        "Re: your message"
    )
    reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"

    # Generate reply — Claude receives pre-extracted routing data, no parsing needed
    print("  Generating reply with Claude...")
    reply_body = generate_reply(thread_id, messages, extracted_data)

    # Send the reply
    result = commune_client.messages.send(
        to=sender,
        subject=reply_subject,
        text=reply_body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    print(f"  Replied to {sender} | message_id={getattr(result, 'message_id', 'ok')}")

    return jsonify({"ok": True})

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    configure_extraction()
    print(f"\nExtraction agent running | inbox: {INBOX_ADDRESS}")
    print("Listening for webhooks on http://0.0.0.0:8000/webhook")
    print("\nTo test locally, expose this port with ngrok:")
    print("  ngrok http 8000")
    print("Then register the public URL as your inbox webhook in the Commune dashboard.\n")
    app.run(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
