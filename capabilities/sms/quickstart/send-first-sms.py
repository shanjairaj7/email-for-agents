"""
Send your first SMS — powered by Commune

Usage:
    export COMMUNE_API_KEY=comm_...
    python send-first-sms.py
"""
import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

numbers = commune.phone_numbers.list()
if not numbers:
    raise SystemExit("No phone numbers found. Provision one at https://commune.email/dashboard")

result = commune.sms.send(
    to="+14155551234",              # replace with your number
    body="Hello from my AI agent!",
    phone_number_id=numbers[0].id,
)

print(f"Sent! Message ID: {result.message_id}")
print(f"      Thread ID:  {result.thread_id}")
print(f"      Status:     {result.status}")
