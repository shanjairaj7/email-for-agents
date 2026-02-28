"""
AI Email Research Agent
========================
An AI agent with its own email inbox that conducts research by emailing
primary sources and synthesising their replies into a markdown report.

Workflow:
  1. Given a research topic, use OpenAI to identify 3-5 relevant contacts
     to reach out to (or read from contacts.json if provided).
  2. Create a dedicated Commune inbox for this research session.
  3. For each contact: draft a thoughtful, specific research question email.
  4. Send each email and track thread_ids in research_state.json.
  5. Poll the inbox for replies (--collect mode).
  6. Synthesise all replies into a structured report saved to report.md.

Usage:
    # Send outreach emails
    python agent.py --topic "Impact of LLMs on legal research workflows"

    # Collect replies and regenerate report (run on a schedule, e.g. hourly)
    python agent.py --topic "Impact of LLMs on legal research workflows" --collect

    # Use a custom contacts file instead of AI-generated contacts
    python agent.py --topic "..." --contacts contacts.json

Environment:
    COMMUNE_API_KEY   — your Commune API key (comm_...)
    OPENAI_API_KEY    — your OpenAI API key
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from commune import CommuneClient
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COMMUNE_API_KEY = os.environ["COMMUNE_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

STATE_FILE = Path(__file__).parent / "research_state.json"
REPORT_FILE = Path(__file__).parent / "report.md"

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[34m"
BOLD = "\033[1m"
RESET = "\033[0m"

def log_info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET}  {msg}")

def log_send(msg: str) -> None:
    print(f"{GREEN}[SEND]{RESET}  {msg}")

def log_reply(msg: str) -> None:
    print(f"{BOLD}{GREEN}[REPLY]{RESET} {msg}")

def log_wait(msg: str) -> None:
    print(f"{YELLOW}[WAIT]{RESET}  {msg}")

def log_report(msg: str) -> None:
    print(f"{BLUE}[REPORT]{RESET} {msg}")

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """
    State shape:
    {
      "topic": "Impact of LLMs on legal research workflows",
      "inbox_id": "inbox_abc123",
      "inbox_address": "research@acme.commune.sh",
      "contacts": [
        {
          "name": "Dr. Jane Smith",
          "email": "j.smith@lawschool.edu",
          "affiliation": "Harvard Law School",
          "rationale": "Published research on AI in legal practice",
          "thread_id": "thread_xyz",
          "replied": false,
          "reply_text": null
        }
      ]
    }
    """
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# OpenAI: identify research contacts
# ---------------------------------------------------------------------------

def identify_contacts(topic: str) -> list[dict]:
    """
    Use OpenAI to generate a list of 4 realistic email contacts to reach out
    to for research on the given topic.

    Returns a list of dicts: name, email, affiliation, rationale.

    Note: These are AI-generated hypothetical contacts for demonstration.
    In production, supply real contacts via --contacts contacts.json.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""I am conducting research on: "{topic}"

Generate a list of 4 realistic hypothetical contacts I could email for primary source research.
These should represent different perspectives: practitioners, academics, journalists, or industry experts.

Return ONLY valid JSON — an array of objects with these exact keys:
  name        (string) — full name
  email       (string) — plausible professional email address
  affiliation (string) — employer or institution
  rationale   (string) — one sentence on why this person is relevant

Example format:
[
  {{
    "name": "Dr. Sarah Chen",
    "email": "s.chen@mit.edu",
    "affiliation": "MIT CSAIL",
    "rationale": "Leads the AI-assisted legal reasoning research group"
  }}
]"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    # The model returns a JSON object — extract the array
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    # Some models wrap in a key — try common patterns
    for key in ("contacts", "results", "sources", "people"):
        if key in parsed:
            return parsed[key]
    # Fallback: return first list value found
    for v in parsed.values():
        if isinstance(v, list):
            return v
    raise ValueError(f"Unexpected JSON shape from OpenAI: {raw[:200]}")


# ---------------------------------------------------------------------------
# OpenAI: draft a research question email for one contact
# ---------------------------------------------------------------------------

def draft_question_email(
    topic: str,
    contact: dict,
    inbox_address: str,
) -> tuple[str, str]:
    """
    Draft a personalised research question email for the given contact.
    Returns (subject, body).
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""Draft a concise, professional research outreach email.

Research topic: {topic}

Contact:
  Name: {contact['name']}
  Affiliation: {contact['affiliation']}
  Why relevant: {contact['rationale']}

Guidelines:
- 3-4 short paragraphs maximum
- Introduce yourself as an independent researcher
- Be specific about what you want to learn from them
- Ask ONE focused question, not a list
- Polite, direct, no flattery
- The reply-to address is: {inbox_address}

Return the subject on line 1 as "Subject: ..." then a blank line then the email body."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    raw = response.choices[0].message.content.strip()
    lines = raw.splitlines()

    subject = f"Research question: {topic}"  # fallback
    body_start = 0

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][len("subject:"):].strip()
        body_start = 2 if len(lines) > 1 and lines[1].strip() == "" else 1

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


# ---------------------------------------------------------------------------
# OpenAI: synthesise all replies into a report
# ---------------------------------------------------------------------------

def synthesise_report(topic: str, contacts: list[dict]) -> str:
    """
    Read all collected replies and synthesise a structured markdown report.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    replied = [c for c in contacts if c.get("replied") and c.get("reply_text")]
    awaiting = [c for c in contacts if not c.get("replied")]

    if not replied:
        return (
            f"# Research Report: {topic}\n\n"
            "_No replies have been received yet. Run with --collect to check for replies._\n"
        )

    source_block = "\n\n".join(
        f"SOURCE: {c['name']} ({c['affiliation']})\n{c['reply_text']}"
        for c in replied
    )

    prompt = f"""You are synthesising primary source responses for a research report.

Research topic: {topic}

Sources that replied ({len(replied)} of {len(contacts)}):

{source_block}

Write a structured markdown research report with:
1. An executive summary (3-5 sentences)
2. Key themes — identify 3-4 recurring themes across the responses
3. Notable quotes — 2-3 direct quotes that capture important insights
4. Divergent views — where do sources disagree or offer contrasting perspectives?
5. Gaps — what questions remain unanswered based on who has not yet replied?
6. Conclusion — 2-3 sentences

Format as clean markdown. Be analytical, not just descriptive."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    report_body = response.choices[0].message.content.strip()

    # Add a header and metadata section
    header = (
        f"# Research Report: {topic}\n\n"
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC_\n\n"
        f"**Sources contacted:** {len(contacts)}  \n"
        f"**Replies received:** {len(replied)}  \n"
        f"**Awaiting reply:** {len(awaiting)}\n\n"
        "---\n\n"
    )

    if awaiting:
        awaiting_section = (
            "\n\n---\n\n## Awaiting Reply\n\n"
            + "\n".join(f"- {c['name']} ({c['affiliation']})" for c in awaiting)
        )
    else:
        awaiting_section = ""

    return header + report_body + awaiting_section


# ---------------------------------------------------------------------------
# Send mode — create inbox, identify contacts, send outreach emails
# ---------------------------------------------------------------------------

def run_send_mode(commune: CommuneClient, topic: str, contacts_file: str | None) -> None:
    state = load_state()

    # If state exists for a different topic, warn the user
    if state and state.get("topic") != topic:
        print(
            f"Warning: research_state.json contains data for a different topic:\n"
            f"  Existing: {state['topic']}\n"
            f"  Current:  {topic}\n"
            "Delete research_state.json to start fresh, or use --collect to continue "
            "the existing session.",
            file=sys.stderr,
        )
        sys.exit(1)

    if state:
        log_info(f"Resuming existing session (inbox: {state['inbox_address']})")
        contacts = state["contacts"]
        inbox_id = state["inbox_id"]
        inbox_address = state["inbox_address"]
    else:
        # Create a new research inbox
        log_info("Creating research inbox …")
        inbox = commune.inboxes.create(local_part="research")
        inbox_id = inbox.id
        inbox_address = inbox.address
        log_info(f"Inbox created: {inbox_address}")

        # Load or generate contacts
        if contacts_file:
            with open(contacts_file) as f:
                contacts = json.load(f)
            log_info(f"Loaded {len(contacts)} contacts from {contacts_file}")
        else:
            log_info("Asking OpenAI to identify research contacts …")
            contacts = identify_contacts(topic)
            log_info(f"Identified {len(contacts)} contacts")

        # Initialise contact state
        for c in contacts:
            c.setdefault("thread_id", None)
            c.setdefault("replied", False)
            c.setdefault("reply_text", None)

        state = {
            "topic": topic,
            "inbox_id": inbox_id,
            "inbox_address": inbox_address,
            "contacts": contacts,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_state(state)

    # Send to contacts that haven't been emailed yet
    sent = 0
    for contact in contacts:
        if contact.get("thread_id"):
            log_info(f"Already sent to {contact['email']} — skipping")
            continue

        log_info(f"Drafting email for {contact['name']} ({contact['affiliation']}) …")
        subject, body = draft_question_email(topic, contact, inbox_address)

        result = commune.messages.send(
            to=contact["email"],
            subject=subject,
            text=body,
            inbox_id=inbox_id,
        )

        contact["thread_id"] = result.thread_id
        save_state(state)  # save after each send

        log_send(f"Sent to {contact['email']} (thread: {result.thread_id})")
        sent += 1

    print(f"\n{BOLD}Outreach complete.{RESET}")
    print(f"  Sent:       {sent}")
    print(f"  Inbox:      {inbox_address}")
    print(f"  State file: {STATE_FILE}")
    print(f"\nRun with --collect to check for replies and generate the report.\n")


# ---------------------------------------------------------------------------
# Collect mode — poll for replies, synthesise report
# ---------------------------------------------------------------------------

def run_collect_mode(commune: CommuneClient, topic: str) -> None:
    state = load_state()

    if not state:
        print("No research session found. Run without --collect first to send outreach emails.", file=sys.stderr)
        sys.exit(1)

    contacts = state["contacts"]
    inbox_id = state["inbox_id"]
    new_replies = 0

    log_info(f"Polling inbox {state['inbox_address']} for replies …")

    for contact in contacts:
        if contact.get("replied"):
            log_info(f"{contact['name']} — already replied, skipping")
            continue

        thread_id = contact.get("thread_id")
        if not thread_id:
            log_info(f"{contact['name']} — no thread_id (not yet sent), skipping")
            continue

        # Fetch thread messages
        try:
            messages = commune.threads.messages(thread_id)
        except Exception as exc:
            print(f"  Could not fetch thread {thread_id}: {exc}", file=sys.stderr)
            continue

        # Look for any inbound message
        for msg in messages:
            if msg.direction == "inbound":
                reply_text = msg.content
                contact["replied"] = True
                contact["reply_text"] = reply_text
                log_reply(f"{contact['name']} replied ({len(reply_text)} chars)")
                new_replies += 1
                break
        else:
            log_wait(f"{contact['name']} — no reply yet")

    save_state(state)

    replied_count = sum(1 for c in contacts if c.get("replied"))
    total = len(contacts)

    print(f"\n{BOLD}Polling complete.{RESET}")
    print(f"  New replies:   {new_replies}")
    print(f"  Total replied: {replied_count}/{total}")

    # Generate report regardless — it will note pending replies
    log_report("Synthesising report …")
    report = synthesise_report(topic, contacts)
    REPORT_FILE.write_text(report)
    log_report(f"Report saved to {REPORT_FILE}")

    if replied_count < total:
        print(f"\n{YELLOW}Tip:{RESET} {total - replied_count} source(s) haven't replied yet.")
        print("Re-run with --collect to check again.\n")
    else:
        print(f"\n{GREEN}All sources have replied.{RESET} Report is complete.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Email Research Agent")
    parser.add_argument("--topic", required=True, help="Research topic or question")
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Poll for replies and regenerate the report (instead of sending)",
    )
    parser.add_argument(
        "--contacts",
        help="Path to a JSON file with contacts to email (skips AI contact generation)",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}AI Email Research Agent{RESET}")
    print(f"Topic:   {args.topic}")
    print(f"Mode:    {'collect' if args.collect else 'send'}")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    commune = CommuneClient(api_key=COMMUNE_API_KEY)

    if args.collect:
        run_collect_mode(commune, args.topic)
    else:
        run_send_mode(commune, args.topic, args.contacts)


if __name__ == "__main__":
    main()
