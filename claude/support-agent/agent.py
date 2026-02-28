"""
Claude Email Support Agent — powered by Commune

Uses Anthropic's tool_use API to give Claude access to Commune email tools.
Claude handles the multi-turn tool loop natively.

Install:
    pip install anthropic commune-mail

Usage:
    export COMMUNE_API_KEY=comm_...
    export ANTHROPIC_API_KEY=sk-ant-...
    python agent.py
"""
import os, json, time
import anthropic
from commune import CommuneClient

commune_client = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Resolve or create inbox
def get_inbox(name: str = "support"):
    for ib in commune_client.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune_client.inboxes.create(local_part=name)
    return ib.id, ib.address

INBOX_ID, INBOX_ADDRESS = get_inbox()

# ── Tool definitions (JSON schema for Claude) ─────────────────────────────────

TOOLS = [
    {
        "name": "list_email_threads",
        "description": "List recent email threads in the support inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max threads to return (default 10)"}
            },
        }
    },
    {
        "name": "get_thread_messages",
        "description": "Get all messages in a thread. Call this to read the full conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "Thread ID from list_email_threads"}
            },
            "required": ["thread_id"]
        }
    },
    {
        "name": "send_reply",
        "description": "Send a reply in an existing email thread. Always include thread_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject (use 'Re: original subject')"},
                "body": {"type": "string", "description": "Email body text"},
                "thread_id": {"type": "string", "description": "Thread ID to reply in (keeps conversation threaded)"}
            },
            "required": ["to", "subject", "body", "thread_id"]
        }
    },
    {
        "name": "search_past_emails",
        "description": "Semantic search across past email threads.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"}
            },
            "required": ["query"]
        }
    }
]

# ── Tool executor ─────────────────────────────────────────────────────────────

def execute_tool(name: str, input_data: dict) -> str:
    if name == "list_email_threads":
        result = commune_client.threads.list(inbox_id=INBOX_ID, limit=input_data.get("limit", 10))
        return json.dumps([{
            "thread_id": t.thread_id, "subject": t.subject,
            "waiting_for_reply": t.last_direction == "inbound",
            "message_count": t.message_count,
        } for t in result.data])

    elif name == "get_thread_messages":
        messages = commune_client.threads.messages(input_data["thread_id"])
        return json.dumps([{
            "direction": m.direction,
            "sender": next((p.identity for p in m.participants if p.role == "sender"), "unknown"),
            "content": m.content,
        } for m in messages])

    elif name == "send_reply":
        result = commune_client.messages.send(
            to=input_data["to"], subject=input_data["subject"],
            text=input_data["body"], inbox_id=INBOX_ID,
            thread_id=input_data["thread_id"]
        )
        return json.dumps({"status": "sent", "message_id": getattr(result, "message_id", "ok")})

    elif name == "search_past_emails":
        results = commune_client.search.threads(query=input_data["query"], inbox_id=INBOX_ID, limit=3)
        return json.dumps([{"thread_id": r.thread_id, "subject": r.subject} for r in results])

    return json.dumps({"error": f"Unknown tool: {name}"})

# ── Agent loop (handles multi-turn tool use) ──────────────────────────────────

def run_agent(task: str, max_turns: int = 10) -> str:
    """Run Claude with tools until it completes the task."""
    messages = [{"role": "user", "content": task}]

    for turn in range(max_turns):
        response = anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=f"""You are a customer support agent. Your inbox: {INBOX_ADDRESS}

Handle inbound emails professionally. Always:
1. Use list_email_threads to find emails waiting for replies
2. Use get_thread_messages to read the full conversation
3. Send replies with send_reply — include thread_id to keep conversations threaded
4. Sign off as "Support Team\"""",
            tools=TOOLS,
            messages=messages,
        )

        # Check if done
        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "Done")
            print(f"\nClaude: {text}")
            return text

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                print(f"  -> {block.name}({json.dumps(block.input, indent=None)[:100]})")
                result = execute_tool(block.name, block.input)
                print(f"     {result[:150]}...")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return "(max turns reached)"

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print(f"Claude support agent running | inbox: {INBOX_ADDRESS}")
    print("Send an email to your inbox address to test.\n")

    handled = set()
    while True:
        result = commune_client.threads.list(inbox_id=INBOX_ID, limit=10)
        unanswered = [t for t in result.data if t.last_direction == "inbound" and t.thread_id not in handled]

        if unanswered:
            print(f"\n{len(unanswered)} email(s) waiting...")
            run_agent("Check the inbox and reply to all unanswered emails. Handle each one completely.")
            for t in unanswered:
                handled.add(t.thread_id)

        time.sleep(30)

if __name__ == "__main__":
    main()
