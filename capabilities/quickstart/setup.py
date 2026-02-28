"""
Full Commune onboarding setup.
Creates an inbox, sends a test email, lists phone numbers, sends a test SMS.
Run this once to verify your account is set up correctly.

Usage:
    COMMUNE_API_KEY=comm_... TEST_EMAIL=you@example.com TEST_PHONE=+1... python setup.py
"""

import os
import sys

from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

TEST_EMAIL = os.environ.get("TEST_EMAIL")
TEST_PHONE = os.environ.get("TEST_PHONE")

print("=" * 50)
print("Commune Setup")
print("=" * 50)

# ---------------------------------------------------------------------------
# 1. Create an inbox
# ---------------------------------------------------------------------------
print("\n[1/4] Creating inbox...")
inbox = commune.inboxes.create(local_part="setup-test")
print(f"  Address : {inbox.address}")
print(f"  Inbox ID: {inbox.id}")

# ---------------------------------------------------------------------------
# 2. Send a test email
# ---------------------------------------------------------------------------
print("\n[2/4] Sending test email...")
if not TEST_EMAIL:
    print("  Skipping — set TEST_EMAIL env var to send a test email.")
else:
    result = commune.messages.send(
        to=TEST_EMAIL,
        subject="Commune setup complete",
        text=(
            "Your Commune account is set up correctly.\n\n"
            "Your agent's email address is: " + inbox.address + "\n\n"
            "You can now receive inbound emails, send threaded replies, "
            "and extract structured data from every message."
        ),
        inbox_id=inbox.id,
    )
    print(f"  Sent to {TEST_EMAIL}")
    print(f"  Thread ID: {result.thread_id}")

# ---------------------------------------------------------------------------
# 3. List phone numbers
# ---------------------------------------------------------------------------
print("\n[3/4] Listing phone numbers...")
numbers = commune.phone_numbers.list()
if not numbers:
    print("  No phone numbers provisioned.")
    print("  Visit https://commune.email/dashboard to provision one.")
else:
    print(f"  Found {len(numbers)} number(s):")
    for n in numbers:
        print(f"    {n.number}  (id: {n.id})")

# ---------------------------------------------------------------------------
# 4. Send a test SMS
# ---------------------------------------------------------------------------
print("\n[4/4] Sending test SMS...")
if not TEST_PHONE:
    print("  Skipping — set TEST_PHONE env var to send a test SMS.")
elif not numbers:
    print("  Skipping — no phone numbers available.")
else:
    sms = commune.sms.send(
        to=TEST_PHONE,
        body="Commune setup complete. SMS is working!",
        phone_number_id=numbers[0].id,
    )
    print(f"  Sent to {TEST_PHONE} from {numbers[0].number}")
    print(f"  SID: {sms.id}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Setup complete.")
print(f"  Inbox address : {inbox.address}")
print(f"  Inbox ID      : {inbox.id}")
if numbers:
    print(f"  Phone number  : {numbers[0].number}")
print()
print("Next steps:")
print("  - Add a webhook: commune.email/dashboard > Inboxes > Webhooks")
print("  - Try email threading: capabilities/email-threading/")
print("  - Try structured extraction: capabilities/structured-extraction/")
print("=" * 50)
