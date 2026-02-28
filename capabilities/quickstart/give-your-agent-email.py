"""
Give your agent an email address.
Creates an inbox and sends a test email to verify it works.
"""

import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Create an inbox — your agent's email address
inbox = commune.inboxes.create(local_part="my-agent")
print(f"Inbox created: {inbox.address}")
print(f"Inbox ID: {inbox.id}")

# Send a test email from your new inbox
result = commune.messages.send(
    to=os.environ["TEST_EMAIL"],  # your own email address
    subject="Hello from my agent",
    text="This email was sent by an AI agent using Commune. It works!",
    inbox_id=inbox.id,
)
print(f"Test email sent. Thread ID: {result.thread_id}")
