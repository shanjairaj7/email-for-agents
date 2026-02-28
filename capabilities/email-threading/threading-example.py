"""
Email Threading Example
Shows the full send-detect-reply cycle:
  1. Create an inbox
  2. Send an opening email (starts a thread)
  3. List threads to find it
  4. Send a follow-up reply in the same thread
  5. Read all messages in the thread
"""

import os
import time

from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# ---------------------------------------------------------------------------
# 1. Create an inbox
# ---------------------------------------------------------------------------
inbox = commune.inboxes.create(local_part="thread-demo")
print(f"Inbox: {inbox.address}")

# ---------------------------------------------------------------------------
# 2. Send the opening message — starts a new thread
# ---------------------------------------------------------------------------
TO_ADDRESS = os.environ["TEST_EMAIL"]  # your own email address

result = commune.messages.send(
    to=TO_ADDRESS,
    subject="Threading demo — message 1",
    text=(
        "Hi,\n\n"
        "This is the first message in a thread.\n\n"
        "The next message from the agent will appear in this same thread "
        "in your inbox — no new email chain.\n\n"
        "— Your agent"
    ),
    inbox_id=inbox.id,
)

thread_id = result.thread_id
print(f"Message 1 sent. Thread ID: {thread_id}")

# ---------------------------------------------------------------------------
# 3. List threads to inspect the thread object
# ---------------------------------------------------------------------------
time.sleep(1)  # give Commune a moment to index
threads = commune.threads.list(inbox_id=inbox.id, limit=5)

print(f"\nThreads in inbox ({len(threads.data)} found):")
for t in threads.data:
    print(f"  thread_id     : {t.thread_id}")
    print(f"  subject       : {t.subject}")
    print(f"  last_direction: {t.last_direction}")
    print(f"  message_count : {t.message_count}")

# ---------------------------------------------------------------------------
# 4. Send a follow-up in the same thread
# ---------------------------------------------------------------------------
print("\nSending follow-up reply in same thread...")
commune.messages.send(
    to=TO_ADDRESS,
    subject="Re: Threading demo — message 1",
    text=(
        "Hi again,\n\n"
        "This is message 2 — same thread_id, so it appears inline "
        "in your inbox under the original email.\n\n"
        "Commune injected In-Reply-To and References headers automatically.\n\n"
        "— Your agent"
    ),
    inbox_id=inbox.id,
    thread_id=thread_id,  # ← same thread
)
print("Message 2 sent (in-thread reply).")

# ---------------------------------------------------------------------------
# 5. Send a third message — agent closes out the conversation
# ---------------------------------------------------------------------------
commune.messages.send(
    to=TO_ADDRESS,
    subject="Re: Threading demo — message 1",
    text=(
        "Hi,\n\n"
        "This is message 3 — still the same thread.\n\n"
        "In a real agent you'd keep replying here as the conversation continues. "
        "When done, call commune.threads.setStatus(thread_id, 'closed') "
        "(TypeScript) to mark the thread resolved.\n\n"
        "— Your agent"
    ),
    inbox_id=inbox.id,
    thread_id=thread_id,
)
print("Message 3 sent.")

# ---------------------------------------------------------------------------
# 6. Read all messages in the thread
# ---------------------------------------------------------------------------
time.sleep(1)
messages = commune.threads.messages(thread_id)

print(f"\nAll messages in thread {thread_id}:")
for i, msg in enumerate(messages, 1):
    direction = "outbound →" if msg.direction == "outbound" else "← inbound"
    preview = msg.content[:60].replace("\n", " ") + "..."
    print(f"  [{i}] {direction} | {msg.created_at} | {preview}")

print("\nDone. Check your inbox — all three messages appear in one thread.")
