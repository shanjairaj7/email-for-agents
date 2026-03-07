# Email Tools for OpenAI Agents SDK

Reusable `@function_tool` definitions for the OpenAI Agents SDK. Import these into any agent instead of rewriting the same boilerplate.

## File

[`email_tools.py`](email_tools.py)

## Tools included

- `read_inbox` — list recent threads from an inbox
- `get_thread` — load full message history for a thread
- `reply_to_thread` — send a reply in an existing thread (passes `thread_id`)
- `search_history` — semantic search across inbox history
- `escalate_to_human` — forward a thread to a human inbox with reason

## Usage

```python
from tools.email_tools import read_inbox, get_thread, reply_to_thread, search_history, escalate_to_human
from agents import Agent

agent = Agent(
    name="Support Agent",
    instructions="...",
    tools=[read_inbox, get_thread, reply_to_thread, search_history, escalate_to_human],
)
```

## Related

- [../support-agent/](../support-agent/) — full agent that uses these tools
- [ADR-001](../../adr/001-use-thread-id-for-all-replies.md) — why `reply_to_thread` always passes `thread_id`
