# OpenAI Agents SDK Email & SMS Examples

The OpenAI Agents SDK's `@function_tool` decorator maps directly onto Commune operations. Define your tools, pass them to the agent, and the model handles tool selection, argument marshalling, and multi-step reasoning — your code just executes the Commune calls.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support Agent](customer_support/) | Support agent reads inbox, reasons over thread history, replies, and escalates to human via email when needed |

---

## Install

```bash
pip install commune-mail openai-agents python-dotenv
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
```

---

## How it works

`@function_tool` introspects the function signature and docstring to build the tool schema the model sees. Return a string and the model continues reasoning. The agent loop handles multi-step calls automatically — read the inbox, read a thread, search history, send reply, all in one `runner.run()` call.

```python
import asyncio
import os
from agents import Agent, Runner, function_tool
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
INBOX_ID = os.environ["COMMUNE_INBOX_ID"]

@function_tool
def list_threads(limit: int = 10) -> str:
    """
    List the most recent email threads in the support inbox.
    Returns thread ID, subject, sender address, and current status for each thread.
    """
    threads = commune.threads.list(inbox_id=INBOX_ID, limit=limit)
    if not threads:
        return "No threads found."
    return "\n".join(
        f"thread_id={t.id} | subject={t.subject!r} | from={t.from_address} | status={t.status}"
        for t in threads
    )

@function_tool
def get_thread_messages(thread_id: str) -> str:
    """
    Retrieve all messages in an email thread by thread ID.
    Always call this before drafting a reply so you have the full conversation context.
    """
    messages = commune.threads.messages(thread_id)
    if not messages:
        return f"No messages found in thread {thread_id}."
    return "\n\n---\n\n".join(
        f"From: {m.from_address}\nDate: {m.created_at}\n\n{m.text}"
        for m in messages
    )

@function_tool
def search_past_threads(query: str) -> str:
    """
    Search past email conversations using semantic similarity.
    Use this to find resolved cases similar to the current issue before drafting a reply.
    """
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=5)
    if not results:
        return "No similar threads found."
    return "\n".join(f"[similarity={r.score:.2f}] {r.subject}" for r in results)

@function_tool
def send_reply(thread_id: str, to: str, subject: str, body: str) -> str:
    """
    Send an email reply into an existing thread.
    Always provide thread_id so the reply is correctly threaded in the recipient's email client.
    """
    msg = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    return f"Reply sent successfully. Message ID: {msg.id}"

@function_tool
def escalate_to_human(thread_id: str, to: str, reason: str) -> str:
    """
    Escalate a support thread to a human agent. Use when the issue is too complex,
    requires account access, involves a refund, or the customer is distressed.
    """
    body = (
        f"This thread has been escalated for human review.\n\n"
        f"Reason: {reason}\n\n"
        f"Thread ID: {thread_id}\n"
        f"Please review and respond to the customer directly."
    )
    msg = commune.messages.send(
        to="humans@yourcompany.com",
        subject=f"[Escalation] Thread {thread_id}",
        text=body,
        inbox_id=INBOX_ID,
    )
    commune.threads.set_status(thread_id, "escalated")
    return f"Thread escalated to human team. Escalation message ID: {msg.id}"

# Define the agent
support_agent = Agent(
    name="Support Agent",
    instructions=(
        "You are a customer support agent with access to the support inbox. "
        "Your workflow: "
        "1. List open threads in the inbox. "
        "2. For each open thread, read the full message history. "
        "3. Search for similar resolved cases to inform your reply. "
        "4. Either send a helpful reply, or escalate to a human if the issue is beyond your scope. "
        "Always thread replies correctly by including the thread_id. "
        "Be concise, professional, and solution-focused."
    ),
    tools=[list_threads, get_thread_messages, search_past_threads, send_reply, escalate_to_human],
    model="gpt-4o",
)

async def main():
    result = await Runner.run(
        support_agent,
        input="Process the support inbox. Reply to any open tickets or escalate if needed.",
    )
    print(result.final_output)

asyncio.run(main())
```

### Handoff pattern

The Agents SDK supports agent handoffs natively. You can route from a triage agent to a specialist:

```python
from agents import Agent, handoff

specialist_agent = Agent(
    name="Billing Specialist",
    instructions="You handle billing disputes and refund requests. You have full account access.",
    tools=[get_thread_messages, send_reply],
    model="gpt-4o",
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="You classify support tickets. Route billing issues to the billing specialist.",
    tools=[list_threads, get_thread_messages],
    handoffs=[handoff(specialist_agent)],
    model="gpt-4o",
)
```

---

## Tips

- Return descriptive strings from tools — the model reads them to decide next steps
- Include `thread_id` in every `send_reply` call; the model will hallucinate thread IDs if you don't enforce it in the docstring
- Use `escalate_to_human` as an explicit exit ramp — prevents the model from looping on unresolvable issues
- Set `model="gpt-4o"` for complex multi-step workflows; `gpt-4o-mini` for high-volume simpler tasks

---

[Back to main README](../README.md)
