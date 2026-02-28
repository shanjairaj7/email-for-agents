"""
SMS marketing campaign tool.

Three modes:
  python campaign.py broadcast [template]   — personalize and send to all non-suppressed contacts
  python campaign.py drip                   — follow up with non-responders after 48 hours
  python campaign.py status                 — show response rates for the current phone number

The broadcast mode checks the Commune suppression list before every send so that
contacts who replied STOP are never messaged again.
"""

import csv
import sys
import time
import datetime
from typing import Optional
from commune import CommuneClient
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# Validate required environment variables at startup.
required_vars = ["COMMUNE_API_KEY", "OPENAI_API_KEY", "PHONE_NUMBER_ID"]
for var in required_vars:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
PHONE_ID = os.environ["PHONE_NUMBER_ID"]
CAMPAIGN_NAME = os.environ.get("CAMPAIGN_NAME", "Campaign")

CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "contacts.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def personalize_message(contact: dict, template: str) -> str:
    """
    Use GPT-4o-mini to personalize a message template for a specific contact.

    This produces natural-sounding messages rather than obvious mail-merge.
    The model is instructed to stay under 160 characters (one SMS segment).
    """
    prompt = (
        f"Personalize this SMS template for the contact below. "
        f"Keep it under 160 characters. Be natural and conversational — "
        f"it should not feel like a template.\n\n"
        f"Template: {template}\n"
        f"Contact: Name={contact.get('name', 'there')}, "
        f"Company={contact.get('company', '')}, "
        f"Role={contact.get('role', '')}\n\n"
        f"Return only the personalized message, nothing else."
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def load_contacts() -> list[dict]:
    """Load contacts from contacts.csv, skipping rows with no phone number."""
    if not os.path.exists(CONTACTS_FILE):
        raise SystemExit(f"contacts.csv not found at {CONTACTS_FILE}")
    with open(CONTACTS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("phone", "").strip()]


# ---------------------------------------------------------------------------
# Broadcast mode: send to all non-suppressed contacts
# ---------------------------------------------------------------------------

def broadcast(template: str, delay: float = 1.0) -> None:
    """
    Send a personalized SMS to every contact not on the suppression list.

    delay: seconds to wait between sends — keeps us under carrier rate limits.
    For large lists, increase this to 1-2 seconds.
    """
    # Fetch opt-out list first. We check this before every send rather than
    # caching it because the list can change (e.g. someone stopped mid-batch).
    suppressed_raw = commune.sms.suppressions(phone_number_id=PHONE_ID)
    suppressed = {s.phone_number for s in suppressed_raw}
    print(f"Suppression list: {len(suppressed)} numbers opted out")

    contacts = load_contacts()
    results = {"sent": 0, "skipped_suppressed": 0, "skipped_no_phone": 0, "failed": 0}

    for contact in contacts:
        phone = contact.get("phone", "").strip()
        name = contact.get("name", phone)

        if not phone:
            results["skipped_no_phone"] += 1
            continue

        if phone in suppressed:
            print(f"  SKIP {name} — opted out")
            results["skipped_suppressed"] += 1
            continue

        try:
            message = personalize_message(contact, template)
        except Exception as e:
            print(f"  FAIL {name} — personalization error: {e}")
            results["failed"] += 1
            continue

        try:
            result = commune.sms.send(
                to=phone,
                body=message,
                phone_number_id=PHONE_ID,
            )
            print(f"  SENT {name} ({phone}): {message[:60]}...")
            results["sent"] += 1
        except Exception as e:
            print(f"  FAIL {name} ({phone}): {e}")
            results["failed"] += 1

        time.sleep(delay)

    print(f"\nBroadcast complete — {CAMPAIGN_NAME}")
    print(f"  Sent:              {results['sent']}")
    print(f"  Skipped (opt-out): {results['skipped_suppressed']}")
    print(f"  Failed:            {results['failed']}")


# ---------------------------------------------------------------------------
# Drip mode: follow up with non-responders after 48 hours
# ---------------------------------------------------------------------------

def check_drip(hours: int = 48, max_sends: int = 10) -> None:
    """
    Find contacts who received an outbound message but haven't replied after
    `hours` hours, then send a follow-up.

    max_sends: caps the number of follow-ups per run to avoid overwhelming people.
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

    # Fetch all active conversations for this phone number
    convos = commune.sms.conversations(phone_number_id=PHONE_ID, limit=200)

    # A thread with message_count == 1 means we sent but they haven't replied.
    # We also check that the last message was sent before the cutoff.
    no_reply = []
    for convo in convos:
        if convo.message_count != 1:
            continue
        try:
            last_at = datetime.datetime.fromisoformat(
                convo.last_message_at.replace("Z", "+00:00")
            ).replace(tzinfo=None)
            if last_at < cutoff:
                no_reply.append(convo)
        except Exception as e:
            print(f"[warn] Could not parse date for {convo.remote_number}: {e}")
            continue

    print(f"Found {len(no_reply)} contacts with no reply after {hours}h")

    sent = 0
    for convo in no_reply[:max_sends]:
        follow_up = (
            "Hey! Just wanted to follow up — did you get a chance to see my message? "
            "Happy to answer any questions."
        )
        try:
            commune.sms.send(
                to=convo.remote_number,
                body=follow_up,
                phone_number_id=PHONE_ID,
            )
            print(f"  Follow-up sent to {convo.remote_number}")
            sent += 1
        except Exception as e:
            print(f"  FAIL {convo.remote_number}: {e}")
        time.sleep(1)

    print(f"\nDrip complete. Follow-ups sent: {sent}")


# ---------------------------------------------------------------------------
# Status mode: show response rates
# ---------------------------------------------------------------------------

def show_status() -> None:
    """
    Fetch all conversations and compute a response rate.

    A thread with message_count > 1 is counted as "replied" (they responded to us).
    """
    convos = commune.sms.conversations(phone_number_id=PHONE_ID, limit=200)
    total = len(convos)

    if total == 0:
        print("No conversations found for this phone number.")
        return

    replied = [c for c in convos if c.message_count > 1]
    unread = [c for c in convos if c.unread_count > 0]
    rate = 100 * len(replied) // total

    print(f"Campaign status — {CAMPAIGN_NAME}")
    print(f"  Total conversations:  {total}")
    print(f"  Replied:             {len(replied)} ({rate}%)")
    print(f"  No reply:            {total - len(replied)}")
    print(f"  Unread:              {len(unread)}")

    if replied:
        print(f"\nMost recent replies:")
        for convo in sorted(replied, key=lambda c: c.last_message_at, reverse=True)[:5]:
            print(f"  {convo.remote_number}: {convo.last_message_preview[:60]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"

    try:
        if mode == "broadcast":
            template = (
                sys.argv[2]
                if len(sys.argv) > 2
                else "Hi {name}! We thought you'd love what we're working on. Want to learn more?"
            )
            broadcast(template)

        elif mode == "drip":
            check_drip()

        elif mode == "status":
            show_status()

        else:
            print("Usage:")
            print('  python campaign.py broadcast "Hi {name}, ..."  — send to all contacts')
            print("  python campaign.py drip                         — follow up non-responders")
            print("  python campaign.py status                       — show response rates")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
