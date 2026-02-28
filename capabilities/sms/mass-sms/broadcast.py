"""
Mass SMS Broadcaster — powered by Commune

Sends personalized SMS to a list of contacts.
Rate limited to avoid carrier throttling.

If OPENAI_API_KEY is set, each message is personalized with gpt-4o-mini.
Otherwise the template is sent as-is.

Usage:
    python broadcast.py --message "Your order has shipped!" --contacts contacts.json
"""
import argparse
import json
import os
import time

from commune import CommuneClient
from openai import OpenAI

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def personalize(template: str, contact: dict) -> str:
    """Optionally personalize message with OpenAI. Falls back to template."""
    if not openai_client.api_key or "{" not in template:
        return template

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Personalize this SMS for {contact['name']}: '{template}'. "
                        "Keep it under 160 characters. Return only the message text, no quotes."
                    ),
                }
            ],
        )
        return response.choices[0].message.content.strip()[:160]
    except Exception:
        # If OpenAI fails, send the original template rather than blocking
        return template


def broadcast(message: str, contacts_file: str) -> None:
    # Get first available phone number
    numbers = commune.phone_numbers.list()
    if not numbers:
        raise ValueError(
            "No phone numbers on this account. "
            "Provision one at https://commune.email/dashboard"
        )
    phone_id = numbers[0].id
    phone_number = numbers[0].number

    # Load contacts
    with open(contacts_file) as f:
        contacts = json.load(f)

    # Filter out opted-out numbers before sending
    suppressions = commune.sms.suppressions(phone_number_id=phone_id)
    opted_out = {s.phone_number for s in suppressions}
    skipped = [c for c in contacts if c["phone"] in opted_out]
    contacts = [c for c in contacts if c["phone"] not in opted_out]

    if skipped:
        print(f"Skipping {len(skipped)} opted-out number(s): {[c['phone'] for c in skipped]}")

    print(f"Sending to {len(contacts)} contacts from {phone_number}...\n")

    sent, failed = [], []

    for contact in contacts:
        try:
            text = personalize(message, contact)
            result = commune.sms.send(
                to=contact["phone"],
                body=text,
                phone_number_id=phone_id,
            )
            sent.append({"phone": contact["phone"], "message_id": result.message_id})
            print(f"  {contact['phone']} — {text[:80]}")

            # ~5 messages/second — stay within carrier rate limits
            time.sleep(0.2)

        except Exception as e:
            failed.append({"phone": contact["phone"], "error": str(e)})
            print(f"  FAILED {contact['phone']} — {e}")

    print(f"\nSent: {len(sent)} | Failed: {len(failed)}")

    if failed:
        print("\nFailed numbers:")
        for f in failed:
            print(f"  {f['phone']} — {f['error']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Broadcast SMS to a contact list via Commune")
    parser.add_argument("--message", required=True, help="Message template to send")
    parser.add_argument("--contacts", default="contacts.json", help="Path to contacts JSON file")
    args = parser.parse_args()

    broadcast(args.message, args.contacts)
