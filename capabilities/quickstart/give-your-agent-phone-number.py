"""
Give your agent a phone number.
Lists provisioned phone numbers and sends a test SMS.
"""

import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# List your provisioned phone numbers
numbers = commune.phone_numbers.list()

if not numbers:
    print("No phone numbers found. Provision one at https://commune.email/dashboard")
    raise SystemExit(1)

print("Your phone numbers:")
for n in numbers:
    print(f"  {n.number}  (id: {n.id})")

# Send a test SMS from the first number
result = commune.sms.send(
    to=os.environ["TEST_PHONE"],  # e.g. "+14155550000"
    body="Hello from your agent! SMS is working.",
    phone_number_id=numbers[0].id,
)
print(f"\nTest SMS sent from {numbers[0].number}. SID: {result.id}")
