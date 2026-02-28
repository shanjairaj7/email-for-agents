"""
Send your first email with Commune.
Creates an inbox then sends an email — the minimal working example.
"""

import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Step 1: Create an inbox (your agent's sending address)
inbox = commune.inboxes.create(local_part="hello-agent")
print(f"Inbox: {inbox.address}")

# Step 2: Send an email
result = commune.messages.send(
    to=os.environ["TEST_EMAIL"],
    subject="My first agent email",
    text=(
        "Hi,\n\n"
        "This was sent by an AI agent using the Commune API.\n\n"
        "To send a follow-up in the same thread, pass thread_id to your next send call.\n\n"
        "— Your agent"
    ),
    inbox_id=inbox.id,
)

# Step 3: Save the thread_id for future replies
print(f"Sent! Message ID: {result.message_id}")
print(f"Thread ID: {result.thread_id}")
print()
print("To reply in the same thread:")
print(f"  commune.messages.send(thread_id='{result.thread_id}', ...)")
