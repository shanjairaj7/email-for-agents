"""
Structured Extraction Webhook Handler
Receives inbound email webhooks from Commune and routes based on extractedData.

Prerequisites:
  1. Run setup-schema.py to configure the extraction schema
  2. Point your Commune inbox webhook at http://your-host/email-webhook
  3. Run: python extraction-example.py

Usage:
    COMMUNE_API_KEY=comm_... COMMUNE_WEBHOOK_SECRET=whsec_... python extraction-example.py
"""

import hashlib
import hmac
import json
import os

from flask import Flask, jsonify, request

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("COMMUNE_WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------

def verify_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify the Commune webhook signature."""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        "sha256",
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def route_support_ticket(message: dict, extracted: dict) -> None:
    intent = extracted.get("intent", "question")
    urgency = extracted.get("urgency", "low")
    order_number = extracted.get("order_number")
    summary = extracted.get("summary", "")
    sender = next(
        (p["identity"] for p in message.get("participants", []) if p["role"] == "sender"),
        "unknown",
    )

    print(f"\n[Support Ticket]")
    print(f"  From     : {sender}")
    print(f"  Intent   : {intent}")
    print(f"  Urgency  : {urgency}")
    print(f"  Order    : {order_number or '—'}")
    print(f"  Summary  : {summary or message.get('content', '')[:80]}")

    if intent == "billing" and urgency == "high":
        print("  → Routing to BILLING (high urgency)")
    elif intent == "cancellation":
        print("  → Routing to RETENTION team")
    elif intent == "bug":
        print("  → Creating ENGINEERING ticket")
    elif intent == "feature_request":
        print("  → Adding to PRODUCT backlog")
    else:
        print("  → Routing to GENERAL support queue")


def route_invoice(message: dict, extracted: dict) -> None:
    vendor = extracted.get("vendor_name", "Unknown vendor")
    invoice_number = extracted.get("invoice_number", "—")
    total = extracted.get("total_amount")
    currency = extracted.get("currency", "USD")
    due_date = extracted.get("due_date", "—")

    print(f"\n[Invoice]")
    print(f"  Vendor   : {vendor}")
    print(f"  Invoice# : {invoice_number}")
    print(f"  Amount   : {currency} {total}")
    print(f"  Due      : {due_date}")
    print(f"  → Routing to ACCOUNTS PAYABLE")


def route_job_application(message: dict, extracted: dict) -> None:
    name = extracted.get("candidate_name", "Unknown")
    role = extracted.get("role_applied_for", "—")
    yoe = extracted.get("years_of_experience")
    skills = extracted.get("skills", [])
    portfolio = extracted.get("portfolio_url")

    print(f"\n[Job Application]")
    print(f"  Candidate : {name}")
    print(f"  Role      : {role}")
    print(f"  Experience: {yoe} years" if yoe else "  Experience: —")
    print(f"  Skills    : {', '.join(skills[:5]) or '—'}")
    if portfolio:
        print(f"  Portfolio : {portfolio}")
    print(f"  → Routing to ATS / RECRUITING queue")


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@app.route("/email-webhook", methods=["POST"])
def handle_email():
    # Optionally verify signature
    if WEBHOOK_SECRET:
        sig = request.headers.get("commune-signature", "")
        if not verify_signature(request.get_data(as_text=True), sig, WEBHOOK_SECRET):
            return jsonify({"error": "Invalid signature"}), 401

    data = request.get_json(force=True)
    message = data.get("message", {})
    extracted = data.get("extractedData") or {}

    print("\n" + "=" * 60)
    print(f"Inbound email received")
    print(f"Thread ID: {message.get('thread_id', '—')}")
    print(f"Extracted: {json.dumps(extracted, indent=2)}")

    # Route based on extracted schema name or fields present
    if "intent" in extracted or "urgency" in extracted:
        route_support_ticket(message, extracted)
    elif "vendor_name" in extracted or "total_amount" in extracted:
        route_invoice(message, extracted)
    elif "candidate_name" in extracted or "years_of_experience" in extracted:
        route_job_application(message, extracted)
    else:
        print("\n[Unclassified] No extraction schema matched — routing to default queue.")

    return jsonify({"status": "ok"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("Structured extraction webhook handler running on http://localhost:5001")
    print("Point your Commune inbox webhook at http://your-host/email-webhook")
    app.run(port=5001, debug=True)
