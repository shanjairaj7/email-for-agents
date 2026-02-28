"""
LangChain Lead Outreach Agent — powered by Commune

Reads leads from leads.csv, crafts personalised outreach emails using an LLM,
sends them via Commune, then monitors for replies and continues conversations.

State is persisted to sent_threads.json so the agent survives restarts.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python agent.py
"""
import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from commune import CommuneClient
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()

# Validate required environment variables at startup
_REQUIRED_ENV = ["COMMUNE_API_KEY", "OPENAI_API_KEY"]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise SystemExit(f"Missing required environment variable: {_var}\n"
                         f"Copy .env.example to .env and fill in your values.")

# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)  # Slightly creative for outreach

HERE = Path(__file__).parent
LEADS_CSV = HERE / "leads.csv"
THREADS_FILE = HERE / "sent_threads.json"

# Delay between individual outreach sends (seconds) — looks more human
SEND_DELAY = int(os.environ.get("SEND_DELAY", "5"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

# ---------------------------------------------------------------------------
# Inbox helpers
# ---------------------------------------------------------------------------

def get_or_create_inbox(name: str = "outreach") -> tuple[str, str]:
    """Return (inbox_id, inbox_address), creating the inbox if it doesn't exist."""
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address


INBOX_NAME = os.environ.get("INBOX_NAME", "outreach")
INBOX_ID, INBOX_ADDRESS = get_or_create_inbox(INBOX_NAME)

# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_thread_state() -> dict:
    """
    Load persisted thread state from disk.
    Schema: { email: { thread_id, lead, status } }
    status values: "sent" | "replied" | "unsubscribed"
    """
    if THREADS_FILE.exists():
        with open(THREADS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_thread_state(state: dict) -> None:
    """Persist thread state to disk."""
    with open(THREADS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_leads() -> list[dict]:
    """Read leads from leads.csv. Expects: name, email, company, role, notes."""
    leads = []
    with open(LEADS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            leads.append({k.strip(): v.strip() for k, v in row.items()})
    return leads

# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

# We build tools as closures so they can reference INBOX_ID at runtime.
# The @tool decorator is applied manually to keep the docstrings intact.

@tool
def compose_outreach_email(lead_json: str) -> str:
    """
    Use the LLM to compose a personalised cold outreach email for a lead.
    Returns a JSON object with 'subject' and 'body'.

    Args:
        lead_json: JSON string with lead fields: name, email, company, role, notes.
    """
    lead = json.loads(lead_json)

    # Inner LLM call — single-shot, no tools needed here
    compose_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)
    response = compose_llm.invoke(
        f"""Write a short, personalised cold outreach email for this lead.

Lead details:
- Name: {lead.get('name')}
- Company: {lead.get('company')}
- Role: {lead.get('role')}
- Notes: {lead.get('notes')}

Guidelines:
- Keep it under 150 words
- Reference their role and company naturally — don't make it feel like a mail merge
- Lead with a relevant observation or compliment, then introduce Beacon briefly
- End with a low-pressure call to action (e.g. "Would it be worth a quick 20-min chat?")
- Do NOT use phrases like "I hope this email finds you well"
- Sign off as "Jordan, Beacon"

Return ONLY valid JSON in this exact format:
{{"subject": "...", "body": "..."}}"""
    )

    # Strip markdown code fences if the model added them
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    Send a new outreach email via Commune.
    Returns JSON with 'status' and 'thread_id'.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.
    """
    result = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
    )
    # Commune returns the thread_id on the message result
    thread_id = getattr(result, "thread_id", getattr(result, "message_id", "unknown"))
    return json.dumps({"status": "sent", "thread_id": thread_id})


@tool
def draft_followup(conversation_json: str) -> str:
    """
    Draft a follow-up reply given the conversation history.
    Returns a JSON object with 'subject' and 'body'.

    Args:
        conversation_json: JSON array of message objects with 'direction' and 'content'.
    """
    messages = json.loads(conversation_json)
    history = "\n\n".join(
        f"[{'Me' if m['direction'] == 'outbound' else 'Them'}]\n{m['content']}"
        for m in messages
    )

    compose_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
    response = compose_llm.invoke(
        f"""You are writing a follow-up reply in an email conversation about Beacon, a team analytics platform.

Conversation so far:
{history}

Write a short, natural follow-up that:
- Acknowledges what they said
- Moves the conversation forward (answer questions, propose a call, etc.)
- Is under 100 words
- Signs off as "Jordan, Beacon"

Return ONLY valid JSON:
{{"subject": "Re: <appropriate subject>", "body": "..."}}"""
    )

    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


@tool
def reply_to_thread(thread_id: str, to: str, subject: str, body: str) -> str:
    """
    Send a reply within an existing email thread.
    Always use this (not send_email) when responding to an existing conversation.

    Args:
        thread_id: The Commune thread ID to reply in.
        to: Recipient email address.
        subject: Reply subject (usually 'Re: <original subject>').
        body: Plain-text reply body.
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

outreach_tools = [compose_outreach_email, send_email]
outreach_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a sales outreach agent for Beacon, a team analytics platform.
Your goal: send a personalised outreach email to a lead.

Steps:
1. Call compose_outreach_email with the lead details as a JSON string.
2. Review the composed email — it should feel natural and relevant.
3. Call send_email to send it. Return the thread_id from the result.

Do not make up information about the lead.""",
    ),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])
outreach_agent = create_tool_calling_agent(llm, outreach_tools, outreach_prompt)
outreach_executor = AgentExecutor(agent=outreach_agent, tools=outreach_tools, verbose=True)

reply_tools = [draft_followup, reply_to_thread]
reply_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a sales agent following up on an outreach email conversation.
Given the conversation history, draft and send an appropriate reply.

Steps:
1. Call draft_followup with the conversation JSON to generate a reply.
2. Call reply_to_thread to send it.

Keep replies concise and human.""",
    ),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])
reply_agent = create_tool_calling_agent(llm, reply_tools, reply_prompt)
reply_executor = AgentExecutor(agent=reply_agent, tools=reply_tools, verbose=True)

# ---------------------------------------------------------------------------
# Outreach phase
# ---------------------------------------------------------------------------

def run_outreach_phase(leads: list[dict], state: dict) -> dict:
    """
    Send initial outreach emails to all leads not yet contacted.
    Updates and returns the thread state dict.
    """
    uncontacted = [l for l in leads if l["email"] not in state]
    if not uncontacted:
        print("All leads already contacted.")
        return state

    print(f"Sending to {len(uncontacted)} new leads...\n")

    for lead in uncontacted:
        print(f"--- Sending to {lead['name']} ({lead['company']}) ---")
        try:
            result = outreach_executor.invoke({
                "input": (
                    f"Send a personalised outreach email to this lead:\n"
                    f"{json.dumps(lead)}\n\n"
                    f"Return the thread_id from send_email."
                )
            })

            # Try to extract thread_id from the agent output
            output_text = result.get("output", "")
            thread_id = None
            try:
                # Agent often returns JSON or mentions the thread_id in output
                data = json.loads(output_text)
                thread_id = data.get("thread_id")
            except (json.JSONDecodeError, TypeError):
                # Fall back: search the output for a thread_id pattern
                import re
                match = re.search(r"thrd_[a-zA-Z0-9_]+", output_text)
                if match:
                    thread_id = match.group(0)

            state[lead["email"]] = {
                "thread_id": thread_id,
                "lead": lead,
                "status": "sent",
            }
            save_thread_state(state)
            print(f"  Sent to {lead['email']} | thread: {thread_id}\n")

        except Exception as exc:  # pylint: disable=broad-except
            print(f"  [error] Failed to send to {lead['email']}: {exc}\n")

        # Brief pause between sends
        if lead != uncontacted[-1]:
            time.sleep(SEND_DELAY)

    return state

# ---------------------------------------------------------------------------
# Reply monitoring phase
# ---------------------------------------------------------------------------

def check_for_replies(state: dict) -> dict:
    """
    Check all tracked threads for inbound replies.
    Draft and send follow-ups where replies are found.
    Returns updated state.
    """
    threads_to_check = {
        email: info
        for email, info in state.items()
        if info.get("status") == "sent" and info.get("thread_id")
    }

    if not threads_to_check:
        return state

    print(f"[check] Scanning {len(threads_to_check)} thread(s) for replies...")

    for email, info in threads_to_check.items():
        thread_id = info["thread_id"]
        try:
            messages = commune.threads.messages(thread_id)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"  [error] Could not fetch thread {thread_id}: {exc}")
            continue

        # Look for any inbound message (customer replied)
        inbound = [m for m in messages if m.direction == "inbound"]
        if not inbound:
            continue

        print(f"  [reply] {email} replied in {thread_id}")

        # Build conversation history for the follow-up agent
        conversation = [
            {"direction": m.direction, "content": m.content}
            for m in messages
        ]

        lead = info.get("lead", {})
        try:
            reply_executor.invoke({
                "input": (
                    f"A lead has replied to our outreach. Continue the conversation.\n\n"
                    f"Lead: {lead.get('name')} <{email}>\n"
                    f"Thread ID: {thread_id}\n\n"
                    f"Conversation history:\n{json.dumps(conversation, indent=2)}\n\n"
                    f"Draft a follow-up and send it using reply_to_thread "
                    f"with thread_id=\"{thread_id}\" and to=\"{email}\"."
                )
            })
            state[email]["status"] = "replied"
            save_thread_state(state)
            print(f"  Follow-up sent to {email}.\n")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"  [error] Failed to send follow-up to {email}: {exc}")

    return state

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Entry point.
    1. Load leads and existing thread state.
    2. Run outreach phase (skips already-contacted leads).
    3. Enter polling loop to monitor for replies.
    """
    print(f"✅ Lead outreach agent running | inbox: {INBOX_ADDRESS}\n")

    leads = load_leads()
    print(f"Loaded {len(leads)} lead(s) from {LEADS_CSV.name}\n")

    state = load_thread_state()

    # Phase 1: outreach
    state = run_outreach_phase(leads, state)

    # Phase 2: reply monitoring loop
    print(f"\nAll leads contacted. Monitoring for replies every {POLL_INTERVAL}s...\n")
    while True:
        try:
            state = check_for_replies(state)
        except KeyboardInterrupt:
            print("\nShutting down agent.")
            break
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[error] {exc}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
