"""
CrewAI Customer Support Crew — powered by Commune

Three agents collaborate to handle inbound support emails:
  1. Triage Agent    — reads inbox, identifies emails needing responses
  2. Research Agent  — searches knowledge base and email history
  3. Reply Agent     — writes and sends the reply

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python main.py
"""
import os
import json
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])


# ── Inbox setup ───────────────────────────────────────────────────────────────

def get_inbox(name: str = "support") -> tuple[str, str]:
    """Resolve an existing inbox by local_part, or create it if it doesn't exist.

    Returns:
        (inbox_id, inbox_address)
    """
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address


INBOX_ID, INBOX_ADDRESS = get_inbox()


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool("List email threads")
def list_threads(limit: int = 10) -> str:
    """List recent email threads in the support inbox.

    Returns a JSON array of thread summaries including thread_id, subject,
    last_direction ('inbound' or 'outbound'), and message_count.
    """
    result = commune.threads.list(inbox_id=INBOX_ID, limit=limit)
    threads = [
        {
            "thread_id": t.thread_id,
            "subject": t.subject,
            "last_direction": t.last_direction,
            "message_count": t.message_count,
        }
        for t in result.data
    ]
    return json.dumps(threads, indent=2)


@tool("Get thread messages")
def get_thread(thread_id: str) -> str:
    """Get all messages in a specific email thread.

    Fetches the complete conversation history for the given thread_id.
    Returns a JSON array of messages with direction, sender email, and
    content (truncated to 500 chars to keep context manageable).
    """
    messages = commune.threads.messages(thread_id)
    result = [
        {
            "direction": m.direction,
            "sender": next(
                (p.identity for p in m.participants if p.role == "sender"),
                "unknown",
            ),
            "content": m.content[:500],
            "created_at": str(m.created_at),
        }
        for m in messages
    ]
    return json.dumps(result, indent=2)


@tool("Search email history")
def search_history(query: str) -> str:
    """Semantic search across past email threads for relevant context.

    Use this to find prior conversations about similar topics — e.g. 'billing
    refund', 'password reset', 'account cancellation'. Returns the top 3 most
    relevant threads by semantic similarity.
    """
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=3)
    return json.dumps(
        [{"thread_id": r.thread_id, "subject": r.subject} for r in results],
        indent=2,
    )


@tool("Send email reply")
def send_reply(to: str, subject: str, body: str, thread_id: str) -> str:
    """Send an email reply inside an existing thread.

    ALWAYS supply thread_id to keep the reply in the customer's thread.
    The reply will appear in the customer's email client as part of the
    same conversation chain.

    Args:
        to:        Recipient email address (the customer's email).
        subject:   Email subject — use 'Re: <original subject>'.
        body:      Plain-text reply body.
        thread_id: The thread to reply into. Do NOT omit this.

    Returns:
        JSON with status and message_id on success.
    """
    result = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    return json.dumps(
        {
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
            "thread_id": thread_id,
        }
    )


# ── Agents ────────────────────────────────────────────────────────────────────

triage_agent = Agent(
    role="Email Triage Specialist",
    goal=(
        "Identify which emails in the inbox need a response and extract the "
        "key details required to handle them."
    ),
    backstory=(
        "You are an expert at scanning busy support inboxes and quickly "
        "identifying what needs attention. You extract the sender's email "
        "address, the subject of their question, the urgency level, and any "
        "specific details that the person replying will need. You never miss "
        "an unanswered inbound email."
    ),
    tools=[list_threads, get_thread],
    verbose=True,
)

research_agent = Agent(
    role="Support Researcher",
    goal=(
        "Find the most relevant information and prior resolutions to help "
        "answer the customer's question thoroughly."
    ),
    backstory=(
        "You are an expert at finding relevant context quickly. You search "
        "the email history for similar past issues and their resolutions, "
        "and synthesise that context into a clear briefing for the person "
        "who will write the reply. You never make things up — if you can't "
        "find relevant context, you say so clearly."
    ),
    tools=[search_history, get_thread],
    verbose=True,
)

reply_agent = Agent(
    role="Customer Reply Specialist",
    goal=(
        "Write and send a professional, helpful, and empathetic reply to "
        "the customer's email."
    ),
    backstory=(
        "You write clear, friendly, and professional customer support emails. "
        "You always address the customer's actual question, never include "
        "filler apologies, and keep replies concise. You ALWAYS reply inside "
        "the existing thread by passing thread_id to send_reply — you never "
        "start a new thread."
    ),
    tools=[send_reply],
    verbose=True,
)


# ── Crew factory ──────────────────────────────────────────────────────────────

def create_support_crew(thread_info: dict) -> Crew:
    """Build and return a sequential crew to handle one email thread.

    Args:
        thread_info: dict with keys 'thread_id' and 'subject'.

    Returns:
        A configured Crew ready for kickoff().
    """
    thread_id = thread_info["thread_id"]
    subject = thread_info["subject"]

    triage_task = Task(
        description=f"""Review this email thread and extract the key information needed to reply.

Thread ID: {thread_id}
Subject: {subject}

Steps:
1. Call get_thread with thread_id="{thread_id}" to read the full conversation.
2. Identify:
   - The sender's email address (from the most recent inbound message)
   - What they are asking or need help with (be specific)
   - Urgency level: low, medium, or high
   - Any relevant details (order numbers, account info, etc.) mentioned in the thread

Be precise. The research and reply agents depend on your output.""",
        expected_output=(
            "A structured summary containing: sender_email, question_or_issue, "
            "urgency (low/medium/high), and key_details (any specific facts from the thread)."
        ),
        agent=triage_agent,
    )

    research_task = Task(
        description="""Using the triage summary from the previous task, find relevant context.

Steps:
1. Formulate 1-2 search queries based on the customer's question.
2. Call search_history for each query to find similar past threads.
3. If a relevant past thread is found, call get_thread to read the resolution.
4. Summarise: what has worked before, what the standard answer is, or what
   additional info you'd need that isn't available.

If no relevant history exists, say so — do not invent answers.""",
        expected_output=(
            "A research briefing: relevant_context (what past threads revealed), "
            "suggested_answer_approach, and any caveats or missing information."
        ),
        agent=research_agent,
        context=[triage_task],
    )

    reply_task = Task(
        description=f"""Write and SEND a professional reply to the customer.

Thread ID: {thread_id}
Subject: {subject}

Using the triage summary (for the sender's email address) and the research
briefing (for the answer), do the following:

1. Write a helpful, concise reply. Address the customer's actual question.
   - Open with a brief acknowledgement (one sentence max).
   - Answer directly and clearly.
   - Close with an offer to help further.
   - Keep total length under 200 words unless the question genuinely requires more.

2. Call send_reply with ALL of these arguments:
   - to: the sender's email (from triage summary)
   - subject: "Re: {subject}"
   - body: your reply text
   - thread_id: "{thread_id}"

The reply MUST be sent — do not just draft it.""",
        expected_output=(
            "Confirmation that the reply was sent, including the message_id "
            "and a copy of the reply body that was sent."
        ),
        agent=reply_agent,
        context=[triage_task, research_task],
    )

    return Crew(
        agents=[triage_agent, research_agent, reply_agent],
        tasks=[triage_task, research_task, reply_task],
        process=Process.sequential,
        verbose=True,
    )
