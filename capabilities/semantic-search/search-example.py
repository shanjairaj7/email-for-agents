"""
Semantic search example — powered by Commune

Shows how to search email threads with natural language queries.
Results are ranked by vector similarity (score 0.0 → 1.0), not keyword matching.

Usage:
    export COMMUNE_API_KEY=comm_...
    python search-example.py
"""
import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Find inbox (create one if needed)
inboxes = commune.inboxes.list()
if not inboxes:
    inbox = commune.inboxes.create(local_part="support")
    inbox_id = inbox.id
    print(f"Created inbox: {inbox.address}")
else:
    inbox_id = inboxes[0].id
    print(f"Using inbox: {inboxes[0].address}")

print()

# Run a few different semantic searches.
# These queries use natural language — they don't need to match the exact words
# in the emails. "customer wants a refund" will surface threads about charge
# disputes, billing errors, money-back requests, and so on.
queries = [
    "customer wants a refund",
    "login or authentication problems",
    "pricing and billing questions",
    "feature request or product feedback",
]

for query in queries:
    print(f"Query: '{query}'")
    results = commune.search.threads(query=query, inbox_id=inbox_id, limit=3)

    if not results:
        print("  No results found (inbox may be empty — send a few emails first)")
    else:
        for r in results:
            subject = r.subject or "(no subject)"
            print(f"  [{r.score:.2f}] {subject} — thread: {r.thread_id}")

    print()
