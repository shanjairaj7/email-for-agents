"""
Send your first SMS with Commune.
Lists available phone numbers and sends a test SMS.
"""

import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Step 1: List your provisioned phone numbers
numbers = commune.phone_numbers.list()
if not numbers:
    print("No phone numbers provisioned.")
    print("Visit https://commune.email/dashboard to provision a number.")
    raise SystemExit(1)

phone = numbers[0]
print(f"Using number: {phone.number} (id: {phone.id})")

# Step 2: Send an SMS
to_number = os.environ["TEST_PHONE"]  # e.g. "+14155550000"
result = commune.sms.send(
    to=to_number,
    body="Hello! This is my first SMS sent via the Commune API.",
    phone_number_id=phone.id,
)

# Step 3: Confirm
print(f"SMS sent to {to_number}")
print(f"Message SID: {result.id}")
