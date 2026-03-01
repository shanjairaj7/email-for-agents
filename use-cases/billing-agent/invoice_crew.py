"""
Billing agent crew — CrewAI multi-agent orchestration for invoice processing.

Receives inbound invoice emails, uses a CrewAI crew to extract line items,
validate totals, and send a confirmation or dispute email to the vendor.

Install:
    pip install flask crewai crewai-tools commune-mail

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    export COMMUNE_WEBHOOK_SECRET=whsec_...
    export COMMUNE_INBOX_ID=i_...
    python invoice_crew.py
"""

import json
import logging
import os

from crewai import Agent, Crew, Task
from crewai.tools import BaseTool
from flask import Flask, jsonify, request
from pydantic import BaseModel

from commune import CommuneClient
from commune.webhooks import verify_signature, WebhookVerificationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBHOOK_SECRET  = os.environ["COMMUNE_WEBHOOK_SECRET"]
COMMUNE_API_KEY = os.environ["COMMUNE_API_KEY"]
INBOX_ID        = os.environ["COMMUNE_INBOX_ID"]

commune = CommuneClient(api_key=COMMUNE_API_KEY)


# ---------------------------------------------------------------------------
# Commune email tools for CrewAI
# ---------------------------------------------------------------------------

class SendEmailInput(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: str = ""


class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = (
        "Send an email to a vendor. Use this to confirm receipt of an invoice "
        "or raise a dispute. Always pass the thread_id so the reply is "
        "correctly threaded in the vendor's email client."
    )
    args_schema: type[BaseModel] = SendEmailInput

    def _run(self, to: str, subject: str, body: str, thread_id: str = "") -> str:
        result = commune.messages.send(
            to=to,
            subject=subject,
            text=body,
            inbox_id=INBOX_ID,
            thread_id=thread_id if thread_id else None,
            idempotency_key=f"invoice-crew-{thread_id}",   # prevents duplicate sends on CrewAI retry
        )
        return f"Email sent. message_id={result.message_id}"


class GetThreadHistoryInput(BaseModel):
    thread_id: str


class GetThreadHistoryTool(BaseTool):
    name: str = "get_thread_history"
    description: str = (
        "Retrieve the full message history for an invoice email thread. "
        "Returns all prior messages with this vendor to provide context."
    )
    args_schema: type[BaseModel] = GetThreadHistoryInput

    def _run(self, thread_id: str) -> str:
        messages = commune.threads.messages(thread_id=thread_id, order="asc")
        if not messages:
            return "No messages found in thread."
        parts = []
        for msg in messages:
            sender = next(
                (p.identity for p in msg.participants if p.role == "sender"),
                "unknown",
            )
            parts.append(f"From: {sender}\nContent: {msg.content}\n---")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# CrewAI agents
# ---------------------------------------------------------------------------

def build_invoice_crew(email_body: str, sender: str, thread_id: str) -> Crew:
    """
    Build a two-agent crew:
    - Extractor: parses invoice data from the email
    - Validator: checks totals and decides confirm vs dispute
    """
    send_tool = SendEmailTool()
    history_tool = GetThreadHistoryTool()

    extractor = Agent(
        role="Invoice Extractor",
        goal="Extract structured invoice data from the email body",
        backstory=(
            "You are a meticulous accountant who reads vendor invoices "
            "and extracts line items, totals, and payment terms."
        ),
        tools=[history_tool],
        verbose=True,
        llm="gpt-4o-mini",
    )

    validator = Agent(
        role="Invoice Validator",
        goal="Validate invoice totals and respond to the vendor",
        backstory=(
            "You are a finance manager who checks that invoice line items "
            "sum to the stated total and sends confirmations or disputes."
        ),
        tools=[send_tool],
        verbose=True,
        llm="gpt-4o-mini",
    )

    # extracted_data comes from Commune's per-inbox JSON Schema extraction —
    # structured fields only, no raw email prose in the agent prompt.
    extract_task = Task(
        description=(
            f"Validate the following structured invoice data extracted from a "
            f"vendor email (thread_id={thread_id}, sender={sender}):\n\n"
            f"Extracted data: {{email_body}}\n\n"
            f"Verify the data is complete. Return a JSON object with: "
            f"invoice_number, vendor_name, total_amount, currency, due_date, line_items."
        ),
        agent=extractor,
        expected_output="A JSON object with the validated invoice fields.",
    )

    validate_task = Task(
        description=(
            f"Given the extracted invoice data, verify that all line_items "
            f"subtotals sum to total_amount. "
            f"If valid: use send_email to confirm receipt to {sender} with thread_id={thread_id}. "
            f"If invalid: use send_email to dispute the total with {sender} with thread_id={thread_id}."
        ),
        agent=validator,
        expected_output="Confirmation that an email was sent to the vendor.",
        context=[extract_task],
    )

    return Crew(
        agents=[extractor, validator],
        tasks=[extract_task, validate_task],
        verbose=True,
        memory=False,  # stateless — safe for concurrent webhook delivery
    )


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------

@app.route("/webhook/billing", methods=["POST"])
def handle_billing_webhook():
    """
    Receive Commune webhook for the billing inbox, run the invoice crew.
    """
    raw_body = request.get_data()
    signature = request.headers.get("X-Commune-Signature", "")
    timestamp = request.headers.get("X-Commune-Timestamp", "")

    try:
        verify_signature(
            payload=raw_body,
            signature=signature,
            secret=WEBHOOK_SECRET,
            timestamp=timestamp,
        )
    except WebhookVerificationError:
        logger.warning("Webhook signature verification failed")
        return jsonify({"error": "Invalid signature"}), 401

    payload = json.loads(raw_body)

    if payload.get("event") != "message.received":
        return jsonify({"status": "ignored"}), 200

    data      = payload.get("data", {})
    message   = data.get("message", {})
    thread_id = data.get("thread_id", "")
    sender    = message.get("from", "")
    body_text = data.get("text", "")

    if not sender or not body_text:
        return jsonify({"status": "skipped"}), 200

    logger.info(f"Invoice email from {sender} on thread {thread_id}")

    crew = build_invoice_crew(
        email_body=body_text,
        sender=sender,
        thread_id=thread_id,
    )
    result = crew.kickoff()
    logger.info(f"Crew result: {result}")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)
