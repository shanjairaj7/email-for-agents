"""
LangChain Customer Support Agent — powered by Commune

Monitors a Commune inbox, responds to inbound emails using a knowledge base.
Polls every 30 seconds. Uses LangChain tool-calling agent pattern.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python agent.py
"""
import os
import json
import glob
import time

from commune import CommuneClient
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ---------------------------------------------------------------------------
# Inbox helpers
# ---------------------------------------------------------------------------

def get_or_create_inbox(name: str = "support") -> tuple[str, str]:
    """Return (inbox_id, inbox_address) for the named inbox, creating it if needed."""
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address


INBOX_NAME = os.environ.get("INBOX_NAME", "support")
INBOX_ID, INBOX_ADDRESS = get_or_create_inbox(INBOX_NAME)

# Path to the local knowledge base directory (sibling of this file)
KB_DIR = os.path.join(os.path.dirname(__file__), "knowledge_base")

# Configurable polling interval (seconds)
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))

# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

@tool
def list_knowledge_base() -> str:
    """
    List all documents available in the knowledge base.
    Returns a JSON array of objects with 'id' and 'title'.
    Call this first to discover what topics are covered before reading a doc.
    """
    docs = []
    for path in sorted(glob.glob(os.path.join(KB_DIR, "*.md"))):
        doc_id = os.path.basename(path).replace(".md", "")
        with open(path, encoding="utf-8") as f:
            # Use the first non-empty line as the title
            title = next(
                (line.strip().lstrip("# ") for line in f if line.strip()),
                doc_id,
            )
        docs.append({"id": doc_id, "title": title})
    return json.dumps(docs, indent=2)


@tool
def read_knowledge_base(doc_id: str) -> str:
    """
    Read the full contents of a knowledge base document.
    Use list_knowledge_base() first to discover valid doc IDs.

    Args:
        doc_id: The document ID (filename without .md extension).
    """
    path = os.path.join(KB_DIR, f"{doc_id}.md")
    if not os.path.exists(path):
        available = [
            os.path.basename(p).replace(".md", "")
            for p in glob.glob(os.path.join(KB_DIR, "*.md"))
        ]
        return json.dumps({
            "error": f"Document '{doc_id}' not found.",
            "available_docs": available,
        })
    with open(path, encoding="utf-8") as f:
        return f.read()


@tool
def search_email_history(query: str) -> str:
    """
    Semantic search over past email threads for relevant context.
    Useful for finding how similar questions were answered previously.

    Args:
        query: Natural language query describing the topic to search for.
    """
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=3)
    if not results:
        return json.dumps({"message": "No relevant past threads found."})
    return json.dumps(
        [
            {
                "thread_id": r.thread_id,
                "subject": r.subject,
                "score": round(r.score, 3),
            }
            for r in results
        ],
        indent=2,
    )


@tool
def send_reply(to: str, subject: str, body: str, thread_id: str) -> str:
    """
    Send an email reply within an existing thread.
    Always pass thread_id to keep the conversation threaded for the customer.

    Args:
        to: Recipient email address.
        subject: Email subject (typically 'Re: <original subject>').
        body: Plain-text reply body. Be helpful and professional.
        thread_id: The thread_id of the conversation being replied to.
    """
    result = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    return json.dumps({
        "status": "sent",
        "message_id": getattr(result, "message_id", "ok"),
    })


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

tools = [list_knowledge_base, read_knowledge_base, search_email_history, send_reply]

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        f"""You are a helpful and professional customer support agent. Your support inbox is: {INBOX_ADDRESS}

When given a support email to handle, follow these steps:
1. Call list_knowledge_base to see what topics are available.
2. Call read_knowledge_base on the most relevant document(s).
3. Optionally call search_email_history to find how similar questions were handled before.
4. Draft a clear, friendly, and accurate reply based on what you found.
5. Send the reply using send_reply — ALWAYS include the thread_id so the reply lands in the right conversation.

Tone: warm, clear, and concise. Avoid jargon. Sign off as "Support Team".
If you cannot find a clear answer in the knowledge base, say so honestly and offer to escalate.""",
    ),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

def process_thread(thread) -> None:
    """Run the agent on a single inbound thread."""
    # Fetch all messages and find the last inbound one
    messages = commune.threads.messages(thread.thread_id)
    last_inbound = next(
        (m for m in reversed(messages) if m.direction == "inbound"), None
    )
    if not last_inbound:
        return

    sender = next(
        (p.identity for p in last_inbound.participants if p.role == "sender"),
        "unknown",
    )
    print(f"\n📨 New email from {sender}: {thread.subject}")

    executor.invoke({
        "input": (
            f"Handle this support email:\n\n"
            f"From: {sender}\n"
            f"Subject: {thread.subject}\n"
            f"Thread ID: {thread.thread_id}\n\n"
            f"{last_inbound.content}\n\n"
            f"Reply to {sender} using send_reply with thread_id=\"{thread.thread_id}\"."
        )
    })


def main() -> None:
    """
    Main polling loop.

    - Maintains a `handled` set so each thread is processed at most once per session.
    - Skips threads whose last message is already outbound (we sent the last message).
    - On error, logs and continues rather than crashing.
    """
    handled: set[str] = set()

    print(f"✅ Support agent running | inbox: {INBOX_ADDRESS}")
    print(f"   Polling every {POLL_INTERVAL}s. Send an email to your inbox to test.\n")

    while True:
        try:
            result = commune.threads.list(inbox_id=INBOX_ID, limit=20)
            for thread in result.data:
                if thread.thread_id in handled:
                    continue

                # Skip threads where we already replied last
                if thread.last_direction == "outbound":
                    handled.add(thread.thread_id)
                    continue

                process_thread(thread)
                handled.add(thread.thread_id)

        except KeyboardInterrupt:
            print("\nShutting down agent.")
            break
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[error] {exc}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
