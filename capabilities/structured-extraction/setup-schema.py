"""
Configure an extraction schema on a Commune inbox.
Run this once at setup time — Commune will then extract structured data
from every inbound email and include it in your webhook payload.

Usage:
    COMMUNE_API_KEY=comm_... COMMUNE_DOMAIN_ID=dom_... COMMUNE_INBOX_ID=inbox_... python setup-schema.py
"""

import json
import os

import requests

API_KEY = os.environ["COMMUNE_API_KEY"]
DOMAIN_ID = os.environ["COMMUNE_DOMAIN_ID"]
INBOX_ID = os.environ["COMMUNE_INBOX_ID"]

BASE_URL = "https://api.commune.email/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def set_extraction_schema(schema_name: str, schema: dict) -> dict:
    """Configure an extraction schema on the inbox."""
    response = requests.put(
        f"{BASE_URL}/domains/{DOMAIN_ID}/inboxes/{INBOX_ID}/extraction-schema",
        headers=HEADERS,
        json={
            "name": schema_name,
            "enabled": True,
            "schema": schema,
        },
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Schema 1: Support ticket
# ---------------------------------------------------------------------------

support_ticket_schema = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["billing", "bug", "feature_request", "cancellation", "question"],
            "description": "The primary intent of the customer's email",
        },
        "urgency": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How urgently the customer needs a response",
        },
        "order_number": {
            "type": "string",
            "description": "Order or transaction ID mentioned in the email",
        },
        "error_message": {
            "type": "string",
            "description": "Any error message or code the customer has included",
        },
        "summary": {
            "type": "string",
            "description": "One-sentence summary of the issue",
        },
    },
}

# ---------------------------------------------------------------------------
# Schema 2: Invoice
# ---------------------------------------------------------------------------

invoice_schema = {
    "type": "object",
    "properties": {
        "vendor_name": {
            "type": "string",
            "description": "Name of the company or person sending the invoice",
        },
        "invoice_number": {
            "type": "string",
            "description": "Invoice or reference number",
        },
        "total_amount": {
            "type": "number",
            "description": "Total amount due (numeric, no currency symbol)",
        },
        "currency": {
            "type": "string",
            "description": "Currency code (USD, EUR, GBP, etc.)",
        },
        "due_date": {
            "type": "string",
            "description": "Payment due date in ISO 8601 format (YYYY-MM-DD)",
        },
        "line_items": {
            "type": "array",
            "description": "Line items on the invoice",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"},
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Schema 3: Job application
# ---------------------------------------------------------------------------

job_application_schema = {
    "type": "object",
    "properties": {
        "candidate_name": {
            "type": "string",
            "description": "Full name of the applicant",
        },
        "role_applied_for": {
            "type": "string",
            "description": "Job title or position the candidate is applying for",
        },
        "years_of_experience": {
            "type": "number",
            "description": "Total years of relevant professional experience",
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technical skills and tools mentioned (e.g. Python, React, SQL)",
        },
        "current_company": {
            "type": "string",
            "description": "Candidate's current or most recent employer",
        },
        "availability": {
            "type": "string",
            "description": "When the candidate can start (e.g. 'immediately', '2 weeks notice')",
        },
        "portfolio_url": {
            "type": "string",
            "description": "Link to portfolio, GitHub, or LinkedIn if mentioned",
        },
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print(f"Configuring extraction schemas on inbox {INBOX_ID}...")
print()

# Choose which schema to configure — uncomment the one you want
schema_options = {
    "support_ticket": support_ticket_schema,
    "invoice": invoice_schema,
    "job_application": job_application_schema,
}

# Default: support ticket. Change this to "invoice" or "job_application".
ACTIVE_SCHEMA = "support_ticket"

result = set_extraction_schema(ACTIVE_SCHEMA, schema_options[ACTIVE_SCHEMA])
print(f"Schema '{ACTIVE_SCHEMA}' configured successfully.")
print(json.dumps(result, indent=2))
print()
print("Every inbound email will now include extractedData in your webhook payload.")
print("Run extraction-example.py to see it in action.")
