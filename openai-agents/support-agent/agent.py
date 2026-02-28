"""
OpenAI Agents SDK — Email Support Agent powered by Commune

Uses OpenAI's official Agents SDK (openai-agents package) with Commune
for email send/receive.

Install:
    pip install openai-agents commune-mail

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python agent.py
"""
import os, json, time
from agents import Agent, Runner, function_tool
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Resolve or create inbox
def get_inbox(name: str = "support"):
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address

INBOX_ID, INBOX_ADDRESS = get_inbox()

# ── Tools ─────────────────────────────────────────────────────────────────────

@function_tool
def list_email_threads(limit: int = 10) -> str:
    """List recent email threads in the support inbox. Returns thread IDs, subjects, and status."""
    result = commune.threads.list(inbox_id=INBOX_ID, limit=limit)
    return json.dumps([{
        "thread_id": t.thread_id,
        "subject": t.subject,
        "waiting_for_reply": t.last_direction == "inbound",
        "message_count": t.message_count,
    } for t in result.data])

@function_tool
def get_thread_messages(thread_id: str) -> str:
    """Get all messages in a thread. Returns sender, direction (inbound/outbound), and content."""
    messages = commune.threads.messages(thread_id)
    return json.dumps([{
        "direction": m.direction,
        "sender": next((p.identity for p in m.participants if p.role == "sender"), "unknown"),
        "content": m.content,
        "created_at": m.created_at,
    } for m in messages])

@function_tool
def send_reply(to: str, subject: str, body: str, thread_id: str) -> str:
    """Reply to an email thread. ALWAYS include thread_id to keep the conversation threaded."""
    result = commune.messages.send(to=to, subject=subject, text=body, inbox_id=INBOX_ID, thread_id=thread_id)
    return json.dumps({"status": "sent", "message_id": getattr(result, "message_id", "ok")})

@function_tool
def search_past_emails(query: str) -> str:
    """Semantic search across past email threads. Use natural language: 'billing refund requests'"""
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=3)
    return json.dumps([{"thread_id": r.thread_id, "subject": r.subject} for r in results])

# ── Agent ─────────────────────────────────────────────────────────────────────

support_agent = Agent(
    name="Email Support Agent",
    instructions=f"""You are a helpful customer support agent. Your email inbox: {INBOX_ADDRESS}

When asked to handle incoming emails:
1. Call list_email_threads to find emails waiting for a reply (waiting_for_reply: true)
2. Call get_thread_messages to read the full conversation
3. Search past emails if context would help
4. Send a reply using send_reply — ALWAYS include the thread_id

Be professional, helpful, and concise. Sign off as "Support Team".""",
    tools=[list_email_threads, get_thread_messages, send_reply, search_past_emails],
    model="gpt-4o-mini",
)

# ── Run ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Support agent running | inbox: {INBOX_ADDRESS}")
    print("Send an email to your inbox address to test.\n")

    handled = set()
    while True:
        result = commune.threads.list(inbox_id=INBOX_ID, limit=10)
        unanswered = [t for t in result.data if t.last_direction == "inbound" and t.thread_id not in handled]

        if unanswered:
            print(f"Found {len(unanswered)} email(s) to handle...")
            run_result = Runner.run_sync(
                support_agent,
                f"Check the inbox and reply to all {len(unanswered)} unanswered email(s)."
            )
            print(f"\nAgent response: {run_result.final_output}")
            for t in unanswered:
                handled.add(t.thread_id)

        time.sleep(30)

if __name__ == "__main__":
    main()
