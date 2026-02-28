# Claude (Anthropic) Email & SMS Examples

Claude's `tool_use` API maps cleanly onto Commune operations. Define tools as JSON schemas, send them with your message, handle `tool_use` content blocks in the response, call the Commune SDK, return `tool_result` blocks — Claude handles the rest.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support Agent](customer_support/) | Claude reads inbox, reasons over thread history, and sends contextual replies |
| [Lead Outreach](lead_outreach/) | Claude personalises and sends cold emails from a contact list |
| [Structured Extraction](structured_extraction/) | Claude uses per-inbox JSON schemas to extract structured data from inbound emails |

---

## Install

```bash
pip install commune-mail anthropic python-dotenv
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## How it works

Define Commune operations as Anthropic tool schemas. Pass them in the `tools` array. When Claude wants to call a tool, the response contains a `tool_use` content block. Execute the Commune SDK call, package the result as a `tool_result` block, and continue the conversation.

```python
import os
import json
import anthropic
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
INBOX_ID = os.environ["COMMUNE_INBOX_ID"]

# Tool definitions — Claude reads these to understand what each tool does and when to use it
TOOLS = [
    {
        "name": "list_threads",
        "description": "List the most recent email threads in the support inbox. "
                       "Returns thread IDs, subjects, sender addresses, and statuses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of threads to return. Default 10.",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_thread_messages",
        "description": "Get all messages in an email thread. Call this before drafting a reply "
                       "to read the full conversation history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "The thread ID to retrieve messages from.",
                }
            },
            "required": ["thread_id"],
        },
    },
    {
        "name": "search_threads",
        "description": "Search past email threads using semantic similarity. "
                       "Useful for finding similar resolved issues before drafting a reply.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "send_reply",
        "description": "Send an email reply into an existing thread. "
                       "Always include thread_id so the reply is correctly threaded.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "Thread to reply into."},
                "to":        {"type": "string", "description": "Recipient email address."},
                "subject":   {"type": "string", "description": "Email subject line."},
                "body":      {"type": "string", "description": "Plain text email body."},
            },
            "required": ["thread_id", "to", "subject", "body"],
        },
    },
]

# Tool executor — maps tool names to Commune SDK calls
def execute_tool(name: str, inputs: dict) -> str:
    if name == "list_threads":
        threads = commune.threads.list(inbox_id=INBOX_ID, limit=inputs.get("limit", 10))
        if not threads:
            return "No threads found."
        return "\n".join(
            f"thread_id={t.id} | {t.subject!r} | from={t.from_address} | status={t.status}"
            for t in threads
        )

    elif name == "get_thread_messages":
        messages = commune.threads.messages(inputs["thread_id"])
        return "\n\n---\n\n".join(
            f"From: {m.from_address}\nDate: {m.created_at}\n\n{m.text}"
            for m in messages
        )

    elif name == "search_threads":
        results = commune.search.threads(query=inputs["query"], inbox_id=INBOX_ID, limit=5)
        if not results:
            return "No similar threads found."
        return "\n".join(f"[score={r.score:.2f}] {r.subject}" for r in results)

    elif name == "send_reply":
        msg = commune.messages.send(
            to=inputs["to"],
            subject=inputs["subject"],
            text=inputs["body"],
            inbox_id=INBOX_ID,
            thread_id=inputs["thread_id"],
        )
        commune.threads.set_status(inputs["thread_id"], "resolved")
        return f"Reply sent. Message ID: {msg.id}. Thread marked resolved."

    return f"Unknown tool: {name}"

# Agentic loop
def run_support_agent():
    messages = [
        {
            "role": "user",
            "content": "Check the support inbox. Read any open threads, search for similar past cases, "
                       "and send helpful replies. Reply only to open threads.",
        }
    ]

    system = (
        "You are a customer support agent with access to the support inbox. "
        "Work through open tickets systematically: read the thread, search for similar resolved cases, "
        "then send a helpful, concise reply. Always include thread_id when replying."
    )

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Append Claude's response to message history
        messages.append({"role": "assistant", "content": response.content})

        # If Claude is done, print final output and exit
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
            break

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  Calling: {block.name}({json.dumps(block.input, indent=2)})")
                result = execute_tool(block.name, block.input)
                print(f"  Result: {result[:200]}{'...' if len(result) > 200 else ''}\n")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # Return tool results to Claude
        messages.append({"role": "user", "content": tool_results})

run_support_agent()
```

### Structured extraction example

Define a JSON schema on your inbox and Claude can query the pre-extracted data instead of parsing raw email text:

```python
# Set a schema on the inbox once
commune.inboxes.update(INBOX_ID, extraction_schema={
    "type": "object",
    "properties": {
        "order_id":   { "type": "string" },
        "issue_type": { "type": "string", "enum": ["damaged", "missing", "wrong_item", "refund"] },
        "urgency":    { "type": "string", "enum": ["low", "medium", "high"] },
    },
})

# Now every inbound message has .extracted populated automatically
# Claude can ask for structured data directly:
@tool — add to TOOLS:
{
    "name": "get_extracted_data",
    "description": "Get the structured data extracted from an email by the Commune extraction schema.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message_id": { "type": "string" }
        },
        "required": ["message_id"],
    },
}

# Handler:
msg = commune.messages.get(inputs["message_id"])
return json.dumps(msg.extracted, indent=2)
```

---

## Tips

- Keep tool descriptions precise — Claude uses them verbatim to decide when to call each tool
- Enforce required fields like `thread_id` in the schema's `"required"` array
- Use `claude-opus-4-6` for complex multi-step workflows; `claude-haiku-3-5` for high-volume simpler classification
- Log tool calls during development (the `print` statements above) — the reasoning trace is invaluable for debugging

---

[Back to main README](../README.md)
