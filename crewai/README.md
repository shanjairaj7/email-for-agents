# CrewAI Email & SMS Examples

CrewAI agents collaborate through shared Commune inboxes. Give each agent its own inbox, or route a crew through a single shared one — agents pass work to each other via threaded email, preserving full conversation history across handoffs.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support Crew](customer_support/) | Triage agent classifies, specialist agent resolves, reply agent sends — pipeline over email |
| [Lead Outreach Crew](lead_outreach/) | Researcher builds profile, writer personalises, sender delivers and tracks |
| [Multi-Agent Coordination](multi_agent/) | Agents assign tasks to each other over email threads with structured handoff payloads |

---

## Install

```bash
pip install commune-mail crewai crewai-tools python-dotenv
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
```

---

## How it works

CrewAI tools use the `@tool` decorator from `crewai.tools`. Each tool wraps a Commune SDK call and returns a string that the agent's LLM can reason about. Agents in a crew can share the same tool set or have separate tools scoped to different inboxes.

```python
import os
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
INBOX_ID = os.environ["COMMUNE_INBOX_ID"]

@tool("Read Inbox Threads")
def read_inbox(limit: int = 10) -> str:
    """Read the most recent threads from the support inbox. Returns thread IDs, subjects, and senders."""
    threads = commune.threads.list(inbox_id=INBOX_ID, limit=limit)
    return "\n".join(f"[{t.id}] Subject: {t.subject} | From: {t.from_address} | Status: {t.status}" for t in threads)

@tool("Get Thread Messages")
def get_thread(thread_id: str) -> str:
    """Retrieve all messages in a thread by its ID. Call this before drafting a reply."""
    messages = commune.threads.messages(thread_id)
    return "\n\n".join(f"[{m.created_at}] From: {m.from_address}\n{m.text}" for m in messages)

@tool("Send Email Reply")
def send_reply(to: str, subject: str, body: str, thread_id: str) -> str:
    """Send an email reply into an existing thread. Requires the thread_id to keep the conversation threaded."""
    msg = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    commune.threads.set_status(thread_id, "resolved")
    return f"Reply sent and thread marked resolved. Message ID: {msg.id}"

@tool("Search Past Threads")
def search_threads(query: str) -> str:
    """Search past email conversations semantically. Use this to find similar resolved cases."""
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=5)
    return "\n".join(f"[score={r.score:.2f}] {r.subject} — {r.snippet}" for r in results)

# Define agents with role-specific tools
triage_agent = Agent(
    role="Triage Specialist",
    goal="Read new support threads and classify each by urgency and category.",
    backstory="You process inbound support tickets and route them accurately.",
    tools=[read_inbox, get_thread, search_threads],
    verbose=True,
)

reply_agent = Agent(
    role="Support Engineer",
    goal="Write clear, helpful replies to support tickets and send them.",
    backstory="You resolve customer issues and communicate solutions professionally.",
    tools=[get_thread, send_reply, search_threads],
    verbose=True,
)

# Define tasks
triage_task = Task(
    description="Read the inbox and identify all open, unanswered threads. "
                "For each thread, read the full message history and produce a summary with: "
                "thread_id, sender email, urgency (low/medium/high), and a one-sentence issue description.",
    expected_output="A list of open threads with their IDs, urgency levels, and issue summaries.",
    agent=triage_agent,
)

reply_task = Task(
    description="For each thread identified as medium or high urgency in the triage output, "
                "search for similar resolved cases, then draft and send a helpful reply. "
                "Always include the thread_id when sending the reply.",
    expected_output="Confirmation of replies sent, with message IDs.",
    agent=reply_agent,
    context=[triage_task],
)

# Run the crew
crew = Crew(
    agents=[triage_agent, reply_agent],
    tasks=[triage_task, reply_task],
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
print(result)
```

### Multi-agent coordination pattern

Agents can hand off work to each other over email — useful for long-running tasks that span multiple agent runs:

```python
@tool("Assign Task to Agent")
def assign_task(to_inbox: str, task_description: str, context: str) -> str:
    """Assign a task to another agent by sending an email to their inbox."""
    msg = commune.messages.send(
        to=to_inbox,
        subject=f"Task: {task_description[:60]}",
        text=f"Task:\n{task_description}\n\nContext:\n{context}",
        inbox_id=INBOX_ID,
    )
    return f"Task assigned. Thread ID for tracking: {msg.thread_id}"
```

Each agent monitors its own inbox, picks up assigned tasks, and replies into the thread when done — creating an auditable, async workflow over email.

---

## Tips

- Use `Process.sequential` for simple pipelines; `Process.hierarchical` for manager-worker patterns
- Give each tool a clear name string (`"Read Inbox Threads"`) — this is what the LLM sees in its reasoning
- Scope tools to inboxes: create separate inboxes per agent role for clean separation
- Pass `context=[triage_task]` to downstream tasks so the output flows automatically

---

[Back to main README](../README.md)
