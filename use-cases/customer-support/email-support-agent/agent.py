"""
AI Email Support Agent — powered by Commune + OpenAI

Standalone polling agent. No framework dependencies.
Polls for inbound emails, searches a local knowledge base,
searches past threads for context, and replies in-thread.

Install:
    pip install -r requirements.txt

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python agent.py
"""

import os
import glob
import time
from pathlib import Path
from openai import OpenAI
from commune import CommuneClient

# ── Clients ────────────────────────────────────────────────────────────────────

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai  = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── Knowledge base directory ───────────────────────────────────────────────────

KB_DIR = Path(__file__).parent / "knowledge_base"

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful customer support agent for Acme SaaS.

Your job is to reply to customer emails in a professional, friendly, and concise way.

Guidelines:
- Answer only what is asked. Don't pad the reply.
- If the answer is in the knowledge base, use it. Quote policies accurately.
- If you don't know the answer, say so honestly and offer to escalate.
- Sign every reply: "— Acme Support Team"
- Do not mention that you are an AI unless directly asked.
- Keep replies under 300 words unless the question genuinely requires more detail.
"""

# ── Terminal colours (no external deps) ────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

def log(colour: str, prefix: str, msg: str) -> None:
    print(f"{colour}{BOLD}[{prefix}]{RESET} {msg}")

# ── Inbox setup ────────────────────────────────────────────────────────────────

def get_or_create_inbox(local_part: str = "support"):
    """
    Return (inbox_id, address) for the named inbox.
    Creates the inbox if it doesn't exist yet — idempotent.
    """
    for inbox in commune.inboxes.list():
        if inbox.local_part == local_part:
            return inbox.id, inbox.address

    inbox = commune.inboxes.create(local_part=local_part)
    return inbox.id, inbox.address

# ── Knowledge base ─────────────────────────────────────────────────────────────

def load_knowledge_base() -> str:
    """
    Read all .md files in knowledge_base/ and concatenate them.
    Returns a single string injected into the system context.
    """
    docs = []
    for path in sorted(glob.glob(str(KB_DIR / "*.md"))):
        name = Path(path).stem
        with open(path) as f:
            content = f.read()
        docs.append(f"=== {name.upper()} ===\n{content}")

    if not docs:
        return "(No knowledge base documents found.)"

    return "\n\n".join(docs)

# ── Thread helpers ─────────────────────────────────────────────────────────────

def get_thread_messages(thread_id: str) -> list[dict]:
    """
    Fetch all messages for a thread and return them as a list of dicts.
    Each dict has: direction, sender, content, created_at.
    """
    messages = commune.threads.messages(thread_id)
    result = []
    for m in messages:
        sender = next(
            (p.identity for p in m.participants if p.role == "sender"),
            "unknown"
        )
        result.append({
            "direction": m.direction,
            "sender":    sender,
            "content":   m.content,
            "created_at": m.created_at,
        })
    return result

def get_last_inbound(messages: list[dict]) -> dict | None:
    """Return the most recent inbound message, or None if there isn't one."""
    for msg in reversed(messages):
        if msg["direction"] == "inbound":
            return msg
    return None

# ── Past-thread search ─────────────────────────────────────────────────────────

def search_past_threads(query: str, inbox_id: str, limit: int = 3) -> str:
    """
    Semantic search over past threads. Returns a formatted string
    summarising the top results (for injection into the LLM context).
    """
    try:
        results = commune.search.threads(query=query, inbox_id=inbox_id, limit=limit)
    except Exception:
        return "(Past thread search unavailable.)"

    if not results:
        return "(No similar past threads found.)"

    lines = ["Similar past threads:"]
    for r in results:
        lines.append(f"  - [{r.thread_id}] {r.subject}")
    return "\n".join(lines)

# ── Reply generation ───────────────────────────────────────────────────────────

def build_chat_messages(
    thread_messages: list[dict],
    kb_context: str,
    past_context: str,
) -> list[dict]:
    """
    Build the message list for the OpenAI chat completion.
    Injects KB and past thread context into the system message,
    then maps each email message to user/assistant turns.
    """
    system = (
        SYSTEM_PROMPT
        + "\n\n--- KNOWLEDGE BASE ---\n"
        + kb_context
        + "\n\n--- PAST SIMILAR THREADS ---\n"
        + past_context
    )

    chat = [{"role": "system", "content": system}]

    for msg in thread_messages:
        role = "user" if msg["direction"] == "inbound" else "assistant"
        chat.append({"role": role, "content": msg["content"]})

    return chat

def generate_reply(chat_messages: list[dict]) -> str:
    """Call OpenAI and return the reply text."""
    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_messages,
    )
    return completion.choices[0].message.content.strip()

# ── Handle a single thread ─────────────────────────────────────────────────────

def handle_thread(thread, inbox_id: str) -> None:
    """
    Process one inbound thread:
    1. Load messages
    2. Find sender
    3. Search KB + past threads
    4. Generate and send reply
    """
    thread_id = thread.thread_id
    subject   = thread.subject or "(no subject)"

    log(CYAN, "THREAD", f"{subject}  [{thread_id}]")

    # 1. Load full thread
    messages = get_thread_messages(thread_id)
    if not messages:
        log(YELLOW, "SKIP", "No messages found — skipping.")
        return

    # 2. Find the sender of the most recent inbound message
    last_inbound = get_last_inbound(messages)
    if not last_inbound:
        log(YELLOW, "SKIP", "No inbound message — skipping.")
        return

    sender  = last_inbound["sender"]
    content = last_inbound["content"]
    log(DIM, "FROM", f"{sender}")
    log(DIM, "MSG", f"{content[:120]}{'...' if len(content) > 120 else ''}")

    # 3. Load context
    kb_context   = load_knowledge_base()
    past_context = search_past_threads(content, inbox_id)

    # 4. Build chat and generate reply
    chat_messages = build_chat_messages(messages, kb_context, past_context)
    reply = generate_reply(chat_messages)

    log(GREEN, "REPLY", f"{reply[:120]}{'...' if len(reply) > 120 else ''}")

    # 5. Send reply in thread (thread_id keeps it in the same chain)
    commune.messages.send(
        to=sender,
        subject=f"Re: {subject}" if not subject.startswith("Re:") else subject,
        text=reply,
        inbox_id=inbox_id,
        thread_id=thread_id,
    )

    log(GREEN, "SENT", f"Reply sent to {sender}")

# ── Main polling loop ──────────────────────────────────────────────────────────

def main() -> None:
    inbox_id, inbox_address = get_or_create_inbox("support")

    log(BOLD, "AGENT", f"Email support agent running")
    log(BOLD, "INBOX", f"{inbox_address}")
    log(DIM,  "INFO",  f"Polling every 30 seconds. Send an email to the inbox above to test.\n")

    # In-memory set of handled thread IDs — resets if you restart the agent.
    # For persistence across restarts, replace this with a database or file.
    handled: set[str] = set()

    while True:
        try:
            result = commune.threads.list(inbox_id=inbox_id, limit=20)

            # Only process threads where the customer sent the last message
            inbound_threads = [
                t for t in result.data
                if t.last_direction == "inbound" and t.thread_id not in handled
            ]

            if inbound_threads:
                log(CYAN, "POLL", f"Found {len(inbound_threads)} new thread(s) to handle")
                for thread in inbound_threads:
                    try:
                        handle_thread(thread, inbox_id)
                        handled.add(thread.thread_id)
                    except Exception as e:
                        log(RED, "ERROR", f"Failed to handle thread {thread.thread_id}: {e}")
            else:
                log(DIM, "POLL", "No new inbound threads — waiting...")

        except Exception as e:
            log(RED, "ERROR", f"Poll error: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()
