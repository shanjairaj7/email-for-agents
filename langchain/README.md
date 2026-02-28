# LangChain Email & SMS Examples

LangChain tools powered by Commune give your chain a real inbox. Decorate a Python function with `@tool` and any LLM in the chain can send emails, read threads, search conversation history, and send SMS — with full type safety and schema documentation that the model actually uses.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support Agent](customer_support/) | Read inbound tickets, classify by urgency, draft and send replies with thread context |
| [Lead Outreach](lead_outreach/) | Pull contacts from a list, personalise outreach using thread history, send and track replies |

---

## Install

```bash
pip install commune-mail langchain-openai langchain-core python-dotenv
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
```

---

## How it works

Commune tools integrate with LangChain through the `@tool` decorator. Each tool gets a docstring that the LLM reads to understand when and how to call it. The model decides which tool to invoke; LangChain routes the call; Commune executes it against the real Commune API.

```python
import os
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

@tool
def send_email(to: str, subject: str, body: str, thread_id: str = None) -> str:
    """Send an email to a user. Optionally supply thread_id to reply within an existing conversation."""
    msg = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=os.environ["COMMUNE_INBOX_ID"],
        thread_id=thread_id,
    )
    return f"Email sent. Message ID: {msg.id}"

@tool
def list_inbox_threads(limit: int = 10) -> str:
    """List the most recent threads in the support inbox. Returns subject, sender, and thread ID."""
    threads = commune.threads.list(inbox_id=os.environ["COMMUNE_INBOX_ID"], limit=limit)
    return "\n".join(f"[{t.id}] {t.subject} — from {t.from_address}" for t in threads)

@tool
def get_thread_messages(thread_id: str) -> str:
    """Get all messages in a thread. Use this before replying to understand the full conversation history."""
    messages = commune.threads.messages(thread_id)
    return "\n\n".join(f"From: {m.from_address}\n{m.text}" for m in messages)

@tool
def search_threads(query: str) -> str:
    """Search past email threads semantically. Useful for finding similar issues or relevant context."""
    results = commune.search.threads(query=query, inbox_id=os.environ["COMMUNE_INBOX_ID"])
    return "\n".join(f"[score={r.score:.2f}] {r.subject}" for r in results)

# Wire tools into a LangChain agent
tools = [send_email, list_inbox_threads, get_thread_messages, search_threads]
llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a customer support agent. You have access to the support inbox. "
               "Read new threads, understand the issue, search for similar past cases, and send helpful replies."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

response = executor.invoke({"input": "Check the inbox and respond to any unanswered support tickets."})
print(response["output"])
```

### What the agent does

1. Calls `list_inbox_threads` to see what's waiting
2. Calls `get_thread_messages` on unanswered threads to read the full conversation
3. Calls `search_threads` to find similar past cases for context
4. Calls `send_email` with `thread_id` to reply — reply lands in the same thread in the user's inbox

---

## Tips

- Pass `thread_id` to `send_email` so replies thread correctly in the user's email client
- Give each tool a precise docstring — the LLM reads it to decide when to call which tool
- Use `search_threads` before replying to surface relevant prior resolutions
- Set `verbose=True` on `AgentExecutor` during development to see the full reasoning trace

---

[Back to main README](../README.md)
