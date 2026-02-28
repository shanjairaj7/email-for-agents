"""
AI Candidate Outreach Agent — powered by Commune

Reads candidates from candidates.csv, sends each one a personalized outreach
email written by OpenAI, then polls for replies and continues the conversation
in the same email thread using Commune's thread_id.

No database required. Commune thread_id is the conversation record.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    export RECRUITER_NAME="Alex Kim"
    export RECRUITER_EMAIL=recruiting@company.com
    python agent.py

Environment:
    COMMUNE_API_KEY    — your Commune API key
    OPENAI_API_KEY     — your OpenAI API key
    RECRUITER_NAME     — name used when signing outreach emails
    RECRUITER_EMAIL    — candidate replies are routed here via Commune inbox
"""
import csv
import json
import os
import time

from commune import CommuneClient
from openai import OpenAI

# ── Clients ────────────────────────────────────────────────────────────────────

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

RECRUITER_NAME = os.environ.get("RECRUITER_NAME", "The Recruiting Team")
RECRUITER_EMAIL = os.environ.get("RECRUITER_EMAIL", "")

# ── File paths ─────────────────────────────────────────────────────────────────

CANDIDATES_FILE = os.path.join(os.path.dirname(__file__), "candidates.csv")
SENT_THREADS_FILE = os.path.join(os.path.dirname(__file__), "sent_threads.json")

# ── Inbox setup ────────────────────────────────────────────────────────────────

def get_inbox() -> tuple[str, str]:
    """Get or create the recruiting inbox."""
    for ib in commune.inboxes.list():
        if ib.local_part == "recruiting":
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part="recruiting")
    return ib.id, ib.address

# ── Candidate data ─────────────────────────────────────────────────────────────

def load_candidates() -> list[dict]:
    """Load candidate list from candidates.csv."""
    with open(CANDIDATES_FILE, newline="") as f:
        return list(csv.DictReader(f))

# ── Sent thread tracking ───────────────────────────────────────────────────────

def load_sent_threads() -> dict:
    """Load the mapping of candidate email -> thread_id."""
    if not os.path.exists(SENT_THREADS_FILE):
        return {}
    with open(SENT_THREADS_FILE) as f:
        return json.load(f)


def save_sent_threads(data: dict) -> None:
    with open(SENT_THREADS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Email generation ───────────────────────────────────────────────────────────

def write_outreach_email(candidate: dict) -> tuple[str, str]:
    """
    Use OpenAI to write a personalized outreach email for this candidate.
    Returns (subject, body).
    """
    context_parts = [
        f"Candidate name: {candidate['name']}",
        f"Role they applied for: {candidate['role_applied']}",
        f"Where we found them: {candidate['resume_source']}",
    ]
    if candidate.get("notes"):
        context_parts.append(f"Notes about them: {candidate['notes']}")

    context = "\n".join(context_parts)

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a personalized recruiting outreach email.\n\n"
                    f"{context}\n\n"
                    f"Recruiter name: {RECRUITER_NAME}\n\n"
                    f"Requirements:\n"
                    f"- Warm, professional tone\n"
                    f"- Mention something specific about their background\n"
                    f"- Briefly describe why this role is interesting\n"
                    f"- Ask if they're open to a quick call\n"
                    f"- Keep the body under 150 words\n"
                    f"- No markdown formatting in the body\n\n"
                    f"Return JSON: {{\"subject\": \"...\", \"body\": \"...\"}}"
                ),
            }
        ],
    )
    result = json.loads(response.choices[0].message.content)
    return result["subject"], result["body"]


def write_follow_up(candidate: dict, thread_history: list[dict]) -> str:
    """
    Given a thread history (list of messages with direction + content),
    use OpenAI to draft an appropriate follow-up reply.
    """
    history_text = "\n\n".join(
        f"[{m['direction'].upper()}]\n{m['content']}"
        for m in thread_history
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are {RECRUITER_NAME}, a recruiter following up with a candidate. "
                    f"Be helpful, warm, and concise. "
                    f"If the candidate wants to schedule a call, propose 2-3 times next week. "
                    f"If they have questions, answer them briefly. "
                    f"If they're not interested, thank them graciously. "
                    f"Keep replies under 100 words. No markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here is the email thread so far with {candidate['name']}:\n\n"
                    f"{history_text}\n\n"
                    f"Write a reply to their latest message."
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()

# ── Outreach ───────────────────────────────────────────────────────────────────

def send_outreach(inbox_id: str) -> None:
    """Send initial outreach emails to all candidates not yet contacted."""
    candidates = load_candidates()
    sent = load_sent_threads()
    newly_sent = 0

    for candidate in candidates:
        email = candidate["email"].strip()
        if email in sent:
            continue  # already contacted

        subject, body = write_outreach_email(candidate)

        result = commune.messages.send(
            to=email,
            subject=subject,
            text=body,
            inbox_id=inbox_id,
        )

        thread_id = getattr(result, "thread_id", None)
        if thread_id:
            sent[email] = {
                "name": candidate["name"],
                "role": candidate["role_applied"],
                "thread_id": thread_id,
            }
            save_sent_threads(sent)
            print(f"  Outreach sent -> {candidate['name']} ({email})")
            print(f"    Subject: {subject}")
            print(f"    thread_id: {thread_id}")
            newly_sent += 1
        else:
            print(f"  Warning: no thread_id returned for {email}")

        time.sleep(0.5)

    if newly_sent == 0:
        print("  All candidates already contacted.")
    else:
        print(f"\n  {newly_sent} outreach email(s) sent.")

# ── Reply handling ─────────────────────────────────────────────────────────────

def handle_replies(inbox_id: str) -> None:
    """
    Check all tracked threads for candidate replies. If the last message is
    inbound (candidate replied), draft and send a follow-up in the same thread.
    """
    sent = load_sent_threads()
    if not sent:
        return

    result = commune.threads.list(inbox_id=inbox_id, limit=50)
    thread_map = {t.thread_id: t for t in result.data}

    for email, info in sent.items():
        thread_id = info.get("thread_id")
        if not thread_id or thread_id not in thread_map:
            continue

        thread = thread_map[thread_id]

        # Only act if the candidate's reply is the most recent message
        if thread.last_direction != "inbound":
            continue

        # Load the full thread to give the LLM the full context
        messages = commune.threads.messages(thread_id)
        history = [
            {"direction": m.direction, "content": m.content or ""}
            for m in messages
        ]

        candidate = {"name": info["name"], "email": email, "role_applied": info["role"]}
        reply_body = write_follow_up(candidate, history)

        # Determine reply subject (Re: original subject)
        original_subject = thread.subject or "Your application"
        reply_subject = (
            original_subject
            if original_subject.lower().startswith("re:")
            else f"Re: {original_subject}"
        )

        commune.messages.send(
            to=email,
            subject=reply_subject,
            text=reply_body,
            inbox_id=inbox_id,
            thread_id=thread_id,  # keeps reply in the same thread
        )
        print(f"  Follow-up sent -> {info['name']} ({email})")
        print(f"    \"{reply_body[:80]}{'...' if len(reply_body) > 80 else ''}\"")

# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    inbox_id, inbox_address = get_inbox()
    print(f"\nCandidate outreach agent")
    print(f"  Inbox:  {inbox_address}")
    print(f"  Recruiter: {RECRUITER_NAME}")
    print(f"  Candidates: {CANDIDATES_FILE}\n")

    # Send initial outreach to any new candidates
    print("Sending outreach...")
    send_outreach(inbox_id)

    # Poll for replies
    print("\nPolling for replies every 60 seconds. Press Ctrl+C to stop.\n")
    while True:
        print("Checking for replies...")
        handle_replies(inbox_id)
        time.sleep(60)


if __name__ == "__main__":
    main()
