"""
AI Cold Outreach Sequence Agent
================================
Runs a personalized multi-step email sequence for each prospect:

  Step 1  (day 0)  — initial outreach, personalized with OpenAI
  Step 2  (day 3)  — first follow-up, sent in the same thread
  Step 3  (day 7)  — breakup email, sent in the same thread

The agent is designed to be run once per day (cron job or manually).
It reads sequence_state.json to determine what needs to be sent today
and skips any prospect that has already replied.

Usage:
    python agent.py

Environment:
    COMMUNE_API_KEY    — your Commune API key (comm_...)
    COMMUNE_INBOX_ID   — the inbox to send from
    OPENAI_API_KEY     — your OpenAI API key
    FROM_NAME          — sender display name
    FROM_COMPANY       — your company name (used in personalization)
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from commune import CommuneClient
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COMMUNE_API_KEY = os.environ["COMMUNE_API_KEY"]
COMMUNE_INBOX_ID = os.environ["COMMUNE_INBOX_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
FROM_NAME = os.getenv("FROM_NAME", "Your Name")
FROM_COMPANY = os.getenv("FROM_COMPANY", "Your Company")

# Days to wait between steps
FOLLOWUP_1_DELAY_DAYS = 3
FOLLOWUP_2_DELAY_DAYS = 7

PROSPECTS_FILE = Path(__file__).parent / "prospects.csv"
STATE_FILE = Path(__file__).parent / "sequence_state.json"
SEQUENCES_DIR = Path(__file__).parent / "sequences"

# ---------------------------------------------------------------------------
# Colour helpers (terminal output)
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

def log_info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET}  {msg}")

def log_send(msg: str) -> None:
    print(f"{GREEN}[SEND]{RESET}  {msg}")

def log_skip(msg: str) -> None:
    print(f"{YELLOW}[SKIP]{RESET}  {msg}")

def log_reply(msg: str) -> None:
    print(f"{BOLD}{GREEN}[REPLY]{RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{RESET} {msg}", file=sys.stderr)

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """
    Load sequence state from disk.

    State shape:
    {
      "sarah.chen@meridianfintech.io": {
        "thread_id": "thread_abc123",
        "step": 1,               # highest step that has been sent
        "sent_at": {
          "1": "2024-01-10T09:00:00+00:00",
          "2": "2024-01-13T09:00:00+00:00"
        },
        "replied": false
      },
      ...
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
# Prospect loading
# ---------------------------------------------------------------------------

def load_prospects() -> list[dict]:
    """Load prospects from CSV and return as a list of dicts."""
    with open(PROSPECTS_FILE, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Email template loading
# ---------------------------------------------------------------------------

def load_template(step: int) -> str:
    names = {1: "initial.txt", 2: "followup_1.txt", 3: "followup_2.txt"}
    path = SEQUENCES_DIR / names[step]
    return path.read_text()


# ---------------------------------------------------------------------------
# OpenAI personalisation
# ---------------------------------------------------------------------------

def personalize_email(prospect: dict, template: str, step: int) -> tuple[str, str]:
    """
    Use OpenAI to fill the template variables and return (subject, body).

    The LLM receives the prospect's name, company, role, and notes and is
    asked to replace the placeholder variables with natural, personalised
    text. The template acts as a structural guide, not a rigid script.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = (
        "You are an expert B2B sales copywriter. "
        "You write short, direct, genuine cold emails — no fluff, no buzzwords. "
        "Emails are 3–5 sentences maximum. "
        "Never use words like 'synergy', 'leverage', 'touch base', or 'circle back'."
    )

    user_prompt = f"""Fill in the following email template for this prospect.
Replace every {{placeholder}} with natural, specific text.
Return ONLY the completed email — nothing else.

PROSPECT:
  Name: {prospect['first_name']} {prospect['last_name']}
  Company: {prospect['company']}
  Role: {prospect['role']}
  Notes: {prospect['notes']}

SENDER:
  Name: {FROM_NAME}
  Company: {FROM_COMPANY}

TEMPLATE (step {step}):
{template}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()

    # Parse subject line from the first line if it starts with "Subject:"
    lines = raw.splitlines()
    subject = f"{prospect['company']} + {FROM_COMPANY}"  # fallback
    body_start = 0

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][len("subject:"):].strip()
        # Skip the blank line between subject and body
        body_start = 2 if len(lines) > 1 and lines[1].strip() == "" else 1

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


# ---------------------------------------------------------------------------
# Reply checking
# ---------------------------------------------------------------------------

def has_replied(commune: CommuneClient, thread_id: str) -> bool:
    """
    Return True if the prospect has sent at least one inbound message on this
    thread. We check last_direction as a fast heuristic — if the last message
    was inbound, the prospect has replied.
    """
    try:
        messages = commune.threads.messages(thread_id)
        for msg in messages:
            if msg.direction == "inbound":
                return True
    except Exception as exc:
        log_error(f"Could not fetch messages for thread {thread_id}: {exc}")
    return False


# ---------------------------------------------------------------------------
# Core sequence logic
# ---------------------------------------------------------------------------

def days_since(iso_timestamp: str) -> float:
    """Return the number of days elapsed since an ISO 8601 timestamp."""
    sent = datetime.fromisoformat(iso_timestamp)
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - sent).total_seconds() / 86400


def run_sequence(commune: CommuneClient, state: dict, prospect: dict) -> None:
    """
    Evaluate and advance the sequence for a single prospect.

    Decision tree:
      - Not in state at all → send step 1
      - Replied               → skip (already done)
      - Step 1 sent, day >= 3, no reply → send step 2
      - Step 2 sent, day >= 7, no reply → send step 3
      - Step 3 sent           → sequence complete, skip
    """
    email = prospect["email"]
    first_name = prospect["first_name"]
    company = prospect["company"]

    entry = state.get(email)

    # ---- Not yet contacted ------------------------------------------------
    if entry is None:
        log_info(f"New prospect: {first_name} at {company} — sending step 1")
        template = load_template(1)
        subject, body = personalize_email(prospect, template, step=1)

        result = commune.messages.send(
            to=email,
            subject=subject,
            text=body,
            inbox_id=COMMUNE_INBOX_ID,
        )

        state[email] = {
            "thread_id": result.thread_id,
            "step": 1,
            "sent_at": {"1": datetime.now(timezone.utc).isoformat()},
            "replied": False,
        }
        log_send(f"Step 1 sent to {email} (thread: {result.thread_id})")
        return

    # ---- Already replied --------------------------------------------------
    if entry.get("replied"):
        log_skip(f"{email} has already replied — sequence complete")
        return

    thread_id = entry["thread_id"]

    # ---- Check for a reply before advancing --------------------------------
    if has_replied(commune, thread_id):
        entry["replied"] = True
        log_reply(f"{email} replied! Stopping sequence.")
        return

    current_step = entry["step"]

    # ---- Sequence complete (step 3 already sent) --------------------------
    if current_step >= 3:
        log_skip(f"{email} — full sequence sent, no reply")
        return

    # ---- Step 2: follow-up 1 at day 3 ------------------------------------
    if current_step == 1:
        elapsed = days_since(entry["sent_at"]["1"])
        if elapsed < FOLLOWUP_1_DELAY_DAYS:
            log_skip(
                f"{email} — step 1 sent {elapsed:.1f}d ago, "
                f"follow-up 1 due in {FOLLOWUP_1_DELAY_DAYS - elapsed:.1f}d"
            )
            return

        log_info(f"{first_name} at {company} — sending step 2 (follow-up 1)")
        template = load_template(2)
        subject, body = personalize_email(prospect, template, step=2)

        commune.messages.send(
            to=email,
            subject=subject,
            text=body,
            inbox_id=COMMUNE_INBOX_ID,
            thread_id=thread_id,  # keeps it in the same thread
        )

        entry["step"] = 2
        entry["sent_at"]["2"] = datetime.now(timezone.utc).isoformat()
        log_send(f"Step 2 sent to {email} (thread: {thread_id})")
        return

    # ---- Step 3: breakup email at day 7 -----------------------------------
    if current_step == 2:
        elapsed = days_since(entry["sent_at"]["1"])  # elapsed since step 1
        if elapsed < FOLLOWUP_2_DELAY_DAYS:
            log_skip(
                f"{email} — step 2 sent, breakup email due in "
                f"{FOLLOWUP_2_DELAY_DAYS - elapsed:.1f}d"
            )
            return

        log_info(f"{first_name} at {company} — sending step 3 (breakup email)")
        template = load_template(3)
        subject, body = personalize_email(prospect, template, step=3)

        commune.messages.send(
            to=email,
            subject=subject,
            text=body,
            inbox_id=COMMUNE_INBOX_ID,
            thread_id=thread_id,
        )

        entry["step"] = 3
        entry["sent_at"]["3"] = datetime.now(timezone.utc).isoformat()
        log_send(f"Step 3 sent to {email} (thread: {thread_id})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{BOLD}Cold Outreach Sequence Agent{RESET}")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    commune = CommuneClient(api_key=COMMUNE_API_KEY)
    prospects = load_prospects()
    state = load_state()

    log_info(f"Loaded {len(prospects)} prospects, {len(state)} already in state")
    print()

    for prospect in prospects:
        run_sequence(commune, state, prospect)

    save_state(state)
    print(f"\n{BOLD}Done.{RESET} State saved to {STATE_FILE}\n")


if __name__ == "__main__":
    main()
