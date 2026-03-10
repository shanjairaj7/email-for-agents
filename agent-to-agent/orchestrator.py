"""
Agent-to-Agent: Orchestrator

Provisions a researcher worker inbox (once), sends a typed research task,
and polls until the worker replies.

Install:
    pip install commune-mail openai

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python orchestrator.py
"""
import os, time, json, hashlib
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])


# ── 1. Resolve or provision inboxes ──────────────────────────────────────────

def get_or_create(local_part: str):
    for ib in commune.inboxes.list():
        if ib.local_part == local_part:
            return ib
    return commune.inboxes.create(local_part=local_part)

orchestrator = get_or_create("orchestrator")
researcher   = get_or_create("researcher")

print(f"Orchestrator : {orchestrator.address}")
print(f"Researcher   : {researcher.address}")


# ── 2. Configure task schema on researcher's inbox (idempotent) ──────────────
# Commune parses every inbound email against this schema before the webhook fires.
# The researcher's webhook receives payload["extracted"] already populated —
# no JSON parsing in the worker.

commune.inboxes.update(researcher.id, extraction_schema={
    "type": "object",
    "required": ["query", "output_format"],
    "properties": {
        "query":         {"type": "string"},
        "output_format": {"type": "string", "enum": ["bullet_points", "prose", "json"]},
        "max_words":     {"type": "integer"},
    }
})


# ── 3. Send the task ──────────────────────────────────────────────────────────

task_description = "Compare pricing and features for managed Postgres hosting (Neon, Supabase, Railway, RDS). Output: bullet_points. Max 300 words."

# Derive a stable idempotency key from the task content — safe to retry
idem_key = "research-" + hashlib.sha256(task_description.encode()).hexdigest()[:12]

task_msg = commune.messages.send(
    to=researcher.address,
    subject="Research task",
    text=task_description,
    inbox_id=orchestrator.id,
    idempotency_key=idem_key,
)

print(f"\nTask sent → thread_id: {task_msg.thread_id}")


# ── 4. Poll until the researcher replies ─────────────────────────────────────
# In production, use a webhook on the orchestrator's inbox instead.

print("Waiting for researcher reply", end="", flush=True)
result = None
for _ in range(24):                          # poll for up to 2 minutes
    time.sleep(5)
    print(".", end="", flush=True)
    messages = commune.threads.messages(task_msg.thread_id)
    outbound_from_researcher = [
        m for m in messages
        if m.direction == "inbound" and len(messages) > 1
    ]
    if outbound_from_researcher:
        result = outbound_from_researcher[-1].content
        break

print()
if result:
    print(f"\nResearcher result:\n{result}")
else:
    print("\nNo reply yet — check researcher.py is running and webhook is configured.")


# ── 5. Read full task chain ───────────────────────────────────────────────────
# The thread preserves the complete provenance: task → result → any follow-up.

messages = commune.threads.messages(task_msg.thread_id)
print(f"\nFull thread ({len(messages)} messages):")
for m in messages:
    direction = "→ sent" if m.direction == "outbound" else "← received"
    print(f"  [{direction}] {(m.content or '')[:80]}")
