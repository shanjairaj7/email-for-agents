"""
Omnichannel Support Agent — Email + SMS
powered by Commune + OpenAI

Single polling loop that handles both email threads and SMS conversations.
Same agent, same knowledge base, same LLM — just different channels.

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
#
# Drop Markdown files here. The agent reads all .md files at reply time.
# Copy knowledge_base/ from ../email-support-agent/ to get started:
#   cp -r ../email-support-agent/knowledge_base ./knowledge_base

KB_DIR = Path(__file__).parent / "knowledge_base"

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful customer support agent for Acme SaaS.
Reply professionally and concisely. Sign off as "— Acme Support".
If you don't know the answer, say so and offer to escalate.
Do not mention that you are an AI unless directly asked.
"""

# ── Terminal colours ───────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RED    = "\033[91m"
DIM    = "\033[2m"

def log(colour: str, prefix: str, msg: str) -> None:
    print(f"{colour}{BOLD}[{prefix}]{RESET} {msg}")

# ── Startup: resolve inbox + phone number ──────────────────────────────────────

def get_or_create_inbox(local_part: str = "support") -> tuple[str, str]:
    """Return (inbox_id, address), creating the inbox if needed."""
    for inbox in commune.inboxes.list():
        if inbox.local_part == local_part:
            return inbox.id, inbox.address
    inbox = commune.inboxes.create(local_part=local_part)
    return inbox.id, inbox.address

def get_phone_number() -> tuple[str | None, str | None]:
    """Return (phone_number_id, number) for the first provisioned number, or (None, None)."""
    numbers = commune.phone_numbers.list()
    if not numbers:
        return None, None
    return numbers[0].id, numbers[0].number

# ── Knowledge base ─────────────────────────────────────────────────────────────

def load_knowledge_base() -> str:
    """Read all .md files in knowledge_base/ and return them as a single string."""
    docs = []
    for path in sorted(glob.glob(str(KB_DIR / "*.md"))):
        name = Path(path).stem
        with open(path) as f:
            content = f.read()
        docs.append(f"=== {name.upper()} ===\n{content}")

    if not docs:
        return "(No knowledge base documents found — add .md files to knowledge_base/.)"

    return "\n\n".join(docs)

# ── Shared LLM call ────────────────────────────────────────────────────────────

def generate_reply(
    chat_history: list[dict],
    kb_context: str,
    max_chars: int | None = None,
) -> str:
    """
    Call OpenAI with the given chat history and KB context.
    max_chars: if set, the system prompt instructs the model to stay within
               that character limit (used for SMS).
    """
    char_limit_note = (
        f"\nIMPORTANT: Keep your reply under {max_chars} characters. Plain text only, no markdown."
        if max_chars else ""
    )

    system = (
        SYSTEM_PROMPT
        + char_limit_note
        + "\n\n--- KNOWLEDGE BASE ---\n"
        + kb_context
    )

    messages = [{"role": "system", "content": system}] + chat_history

    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )
    return completion.choices[0].message.content.strip()

# ── Email handling ─────────────────────────────────────────────────────────────

def is_new_inbound_email(thread, handled_emails: set[str]) -> bool:
    """True if this thread has an unanswered inbound message we haven't handled yet."""
    return (
        thread.last_direction == "inbound"
        and thread.thread_id not in handled_emails
    )

def handle_email_thread(thread, inbox_id: str, kb_context: str) -> None:
    """
    Handle one email thread:
    1. Load messages
    2. Build chat history
    3. Generate reply with KB context
    4. Send reply in-thread via Commune
    """
    thread_id = thread.thread_id
    subject   = thread.subject or "(no subject)"

    log(CYAN, "EMAIL", f"{subject}  [{thread_id}]")

    # Load all messages in the thread
    raw_messages = commune.threads.messages(thread_id)
    if not raw_messages:
        log(YELLOW, "SKIP", "Empty thread — skipping.")
        return

    # Find sender of most recent inbound message
    sender = None
    for msg in reversed(raw_messages):
        if msg.direction == "inbound":
            sender = next(
                (p.identity for p in msg.participants if p.role == "sender"),
                None
            )
            break

    if not sender:
        log(YELLOW, "SKIP", "Could not determine sender — skipping.")
        return

    log(DIM, "FROM", sender)

    # Build OpenAI chat history from thread messages
    chat_history = [
        {
            "role":    "user" if m.direction == "inbound" else "assistant",
            "content": m.content,
        }
        for m in raw_messages
    ]

    # Generate reply (no character limit for email)
    reply = generate_reply(chat_history, kb_context)

    log(GREEN, "REPLY", f"{reply[:100]}{'...' if len(reply) > 100 else ''}")

    # Send reply — thread_id keeps it in the same email chain
    commune.messages.send(
        to=sender,
        subject=f"Re: {subject}" if not subject.startswith("Re:") else subject,
        text=reply,
        inbox_id=inbox_id,
        thread_id=thread_id,
    )

    log(GREEN, "SENT", f"Email reply sent to {sender}")

# ── SMS handling ───────────────────────────────────────────────────────────────

def is_new_inbound_sms(convo, handled_sms: set[str]) -> bool:
    """
    True if the most recent message in this SMS conversation is inbound
    and we haven't handled it yet.

    Each SMS conversation object has a `remote_number` (the customer's number)
    and a `last_message_direction` field, or we check the last message directly.
    """
    remote = getattr(convo, "remote_number", None) or getattr(convo, "from_number", None)
    if not remote or remote in handled_sms:
        return False

    # Check last direction — attribute name varies; try common ones
    last_dir = (
        getattr(convo, "last_message_direction", None)
        or getattr(convo, "last_direction", None)
    )
    if last_dir:
        return last_dir == "inbound"

    # Fallback: assume new conversations are inbound
    return True

def handle_sms_conversation(convo, phone_number_id: str, kb_context: str, max_sms_chars: int = 160) -> None:
    """
    Handle one SMS conversation:
    1. Load full conversation history
    2. Build chat history
    3. Generate reply (≤160 chars)
    4. Send reply via Commune SMS
    """
    remote_number = (
        getattr(convo, "remote_number", None)
        or getattr(convo, "from_number", None)
    )
    if not remote_number:
        log(YELLOW, "SKIP", "Could not determine remote number — skipping SMS convo.")
        return

    log(BLUE, "SMS", f"Conversation with {remote_number}")

    # Load full SMS thread between our number and this customer
    history = commune.sms.thread(
        remote_number=remote_number,
        phone_number_id=phone_number_id,
    )

    if not history:
        log(YELLOW, "SKIP", "Empty SMS thread — skipping.")
        return

    # Map to OpenAI chat turns
    chat_history = [
        {
            "role":    "user" if m.direction == "inbound" else "assistant",
            "content": m.body,
        }
        for m in history
    ]

    last_msg = history[-1].body if history else ""
    log(DIM, "LAST", f"{last_msg[:80]}{'...' if len(last_msg) > 80 else ''}")

    # Generate reply — with character limit for SMS
    reply = generate_reply(chat_history, kb_context, max_chars=max_sms_chars)

    # Truncate hard if the model went over (shouldn't happen, but safe)
    if len(reply) > max_sms_chars:
        reply = reply[: max_sms_chars - 3] + "..."

    log(GREEN, "REPLY", f"({len(reply)} chars) {reply}")

    # Send the reply via Commune SMS
    commune.sms.send(
        to=remote_number,
        body=reply,
        phone_number_id=phone_number_id,
    )

    log(GREEN, "SENT", f"SMS reply sent to {remote_number}")

# ── Main polling loop ──────────────────────────────────────────────────────────

def main() -> None:
    # Startup
    inbox_id, inbox_address = get_or_create_inbox("support")
    phone_id, phone_number  = get_phone_number()

    log(BOLD, "AGENT", "Omnichannel support agent starting")
    log(BOLD, "EMAIL", f"{inbox_address}")
    if phone_number:
        log(BOLD, "SMS  ", f"{phone_number}")
    else:
        log(YELLOW, "SMS  ", "No phone number found — SMS handling disabled. Provision one at commune.sh/dashboard.")
    print()

    # In-memory tracking of handled conversations.
    # Resets on restart. Replace with a DB for persistence.
    handled_emails: set[str] = set()
    handled_sms:    set[str] = set()

    while True:
        try:
            # Load KB once per cycle (cheap — files are local)
            kb_context = load_knowledge_base()

            # ── Email ──────────────────────────────────────────────────────────

            email_result = commune.threads.list(inbox_id=inbox_id, limit=10)
            new_email_threads = [
                t for t in email_result.data
                if is_new_inbound_email(t, handled_emails)
            ]

            if new_email_threads:
                log(CYAN, "POLL", f"Email: {len(new_email_threads)} new thread(s)")
                for thread in new_email_threads:
                    try:
                        handle_email_thread(thread, inbox_id, kb_context)
                        handled_emails.add(thread.thread_id)
                    except Exception as e:
                        log(RED, "ERROR", f"Email thread {thread.thread_id}: {e}")

            # ── SMS ────────────────────────────────────────────────────────────

            if phone_id:
                sms_convos = commune.sms.conversations(phone_number_id=phone_id)
                new_sms_convos = [
                    c for c in sms_convos
                    if is_new_inbound_sms(c, handled_sms)
                ]

                if new_sms_convos:
                    log(BLUE, "POLL", f"SMS: {len(new_sms_convos)} new conversation(s)")
                    for convo in new_sms_convos:
                        remote = (
                            getattr(convo, "remote_number", None)
                            or getattr(convo, "from_number", None)
                        )
                        try:
                            handle_sms_conversation(convo, phone_id, kb_context)
                            if remote:
                                handled_sms.add(remote)
                        except Exception as e:
                            log(RED, "ERROR", f"SMS convo {remote}: {e}")

            # ── Quiet cycle ────────────────────────────────────────────────────

            if not new_email_threads and (not phone_id or not new_sms_convos):
                log(DIM, "POLL", "No new messages — waiting 30s...")

        except Exception as e:
            log(RED, "ERROR", f"Poll loop error: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()
