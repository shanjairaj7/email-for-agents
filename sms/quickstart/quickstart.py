"""
SMS Quickstart — send your first text in 60 seconds.

Steps:
  1. List phone numbers to find one with SMS capability
  2. Send a test SMS to TEST_PHONE_NUMBER
  3. Print the delivery receipt

Usage:
  python quickstart.py
"""

import os
import sys
from dotenv import load_dotenv
from commune import CommuneClient

load_dotenv()

# Validate required environment variables before doing anything else.
# Failing fast here gives a clear error rather than a confusing API response.
required = ["COMMUNE_API_KEY", "TEST_PHONE_NUMBER"]
for var in required:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

API_KEY = os.environ["COMMUNE_API_KEY"]
TEST_PHONE = os.environ["TEST_PHONE_NUMBER"]

commune = CommuneClient(api_key=API_KEY)


def find_sms_capable_number():
    """Return the first phone number on the account that has SMS capability."""
    numbers = commune.phone_numbers.list()

    if not numbers:
        raise SystemExit(
            "No phone numbers found on your account. "
            "Provision one at https://commune.sh before running this script."
        )

    for number in numbers:
        # Skip numbers that don't have SMS enabled (e.g. voice-only lines)
        if number.capabilities and number.capabilities.sms:
            return number

    raise SystemExit(
        "No SMS-capable phone numbers found. "
        "Check your Commune dashboard and ensure at least one number has SMS enabled."
    )


def main() -> None:
    print("Fetching phone numbers...")
    phone = find_sms_capable_number()
    print(f"Using phone number: {phone.number}  (id={phone.id})")

    print(f"\nSending SMS to {TEST_PHONE}...")
    try:
        result = commune.sms.send(
            to=TEST_PHONE,
            body="Hello from Commune! Your SMS quickstart is working.",
            phone_number_id=phone.id,
        )
    except Exception as e:
        raise SystemExit(f"SMS send failed: {e}")

    # Print the full delivery receipt so you can verify everything looks right.
    print("\nDelivery receipt:")
    print(f"  message_id      = {result.message_id}")
    print(f"  thread_id       = {result.thread_id}")
    print(f"  status          = {result.status}")
    print(f"  credits_charged = {result.credits_charged}")
    print(f"  segments        = {result.segments}")
    print("\nDone. Check your phone for the message.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
