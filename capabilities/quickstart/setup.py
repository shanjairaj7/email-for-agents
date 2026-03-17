"""
Full Commune onboarding setup.
Creates an inbox and sends a test email.
Run this once to verify your account is set up correctly.

Usage:
    COMMUNE_API_KEY=comm_... TEST_EMAIL=you@example.com python setup.py
"""

import os
import sys

from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

TEST_EMAIL = os.environ.get("TEST_EMAIL")

print("=" * 50)
print("Commune Setup")
print("=" * 50)

# ---------------------------------------------------------------------------
# 1. Create an inbox
# ---------------------------------------------------------------------------
print("\n[1/2] Creating inbox...")
inbox = commune.inboxes.create(local_part="setup-test")
print(f"  Address : {inbox.address}")
print(f"  Inbox ID: {inbox.id}")

# ---------------------------------------------------------------------------
# 2. Send a test email
# ---------------------------------------------------------------------------
print("\n[2/2] Sending test email...")
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
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Setup complete.")
print(f"  Inbox address : {inbox.address}")
print(f"  Inbox ID      : {inbox.id}")
print()
print("Next steps:")
print("  - Add a webhook: commune.email/dashboard > Inboxes > Webhooks")
print("  - Try email threading: capabilities/email-threading/")
print("  - Try structured extraction: capabilities/structured-extraction/")
print("=" * 50)
