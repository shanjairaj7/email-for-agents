"""
Phone number management — powered by Commune

Shows how to list phone numbers, send an SMS, and read SMS conversations.

Note: provisioning new phone numbers requires the Commune dashboard
or the TypeScript phoneNumbers.provision() method. See manage-numbers.ts.

Usage:
    export COMMUNE_API_KEY=comm_...
    python manage-numbers.py
"""
import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# ── List phone numbers ─────────────────────────────────────────────────────────

print("Phone numbers on your account:")
numbers = commune.phone_numbers.list()

if not numbers:
    print("  No phone numbers found.")
    print("  Provision one at https://commune.email/dashboard or use manage-numbers.ts")
    raise SystemExit(0)

for n in numbers:
    sms_cap   = "SMS" if n.capabilities.sms   else "no SMS"
    voice_cap = "Voice" if n.capabilities.voice else "no Voice"
    print(f"  {n.number}  [{sms_cap}, {voice_cap}]  id={n.id}")

phone = numbers[0]
print()

# ── Send an SMS ────────────────────────────────────────────────────────────────

# Replace with a real number you own for testing
recipient = "+14155551234"

print(f"Sending SMS to {recipient} from {phone.number}...")
result = commune.sms.send(
    to=recipient,
    body="Hello from your Commune agent!",
    phone_number_id=phone.id,
)
print(f"  Sent — message_id: {result.message_id}")
print(f"         thread_id:  {result.thread_id}")
print(f"         status:     {result.status}")
print(f"         credits:    {result.credits_charged}")
print()

# ── List conversations ─────────────────────────────────────────────────────────

print(f"Conversations on {phone.number}:")
conversations = commune.sms.conversations(phone_number_id=phone.id)

if not conversations:
    print("  No conversations yet.")
else:
    for convo in conversations:
        print(f"  {convo.remote_number}  ({convo.message_count} messages)")
        print(f"    Last: {convo.last_message_preview}")
        print(f"    Thread: {convo.thread_id}")
        print()

# ── Read a specific conversation thread ───────────────────────────────────────

if conversations:
    first = conversations[0]
    print(f"Full thread with {first.remote_number}:")
    messages = commune.sms.thread(
        remote_number=first.remote_number,
        phone_number_id=phone.id,
    )
    for msg in messages:
        direction = "OUT" if msg.direction == "outbound" else " IN"
        print(f"  [{direction}] {msg.created_at}  {msg.content}")
