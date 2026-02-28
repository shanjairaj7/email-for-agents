"""
AI Newsletter Agent
====================
Generates and sends a personalised newsletter to every subscriber.

Usage:
    python agent.py --topic "AI tools for developers" --issue 1
    python agent.py --topic "AI tools for developers" --issue 1 --test-email you@company.com

Arguments:
    --topic         Topic or theme for this issue (required)
    --issue         Issue number, used for deduplication (required)
    --test-email    Send only to this address instead of the full list

Commune automatically adds List-Unsubscribe and List-Unsubscribe-Post headers
on every outbound message, so one-click unsubscribe works in Gmail, Apple Mail,
and Outlook without any extra work on your end.

Environment:
    COMMUNE_API_KEY    — your Commune API key (comm_...)
    COMMUNE_INBOX_ID   — the inbox to send from
    OPENAI_API_KEY     — your OpenAI API key
    NEWSLETTER_NAME    — display name for the newsletter (default: The Weekly Dispatch)
    FROM_NAME          — sender display name
"""

import argparse
import csv
import json
import os
import sys
import time
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
COMMUNE_INBOX_ID = os.environ["COMMUNE_INBOX_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NEWSLETTER_NAME = os.getenv("NEWSLETTER_NAME", "The Weekly Dispatch")
FROM_NAME = os.getenv("FROM_NAME", "Your Name")

SUBSCRIBERS_FILE = Path(__file__).parent / "subscribers.csv"
LOG_FILE = Path(__file__).parent / "newsletter_log.json"

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

def log_info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET}  {msg}")

def log_send(msg: str) -> None:
    print(f"{GREEN}[SEND]{RESET}  {msg}")

def log_skip(msg: str) -> None:
    print(f"{YELLOW}[SKIP]{RESET}  {msg}")

# ---------------------------------------------------------------------------
# Log helpers — track (email, issue) pairs that have been sent
# ---------------------------------------------------------------------------

def load_log() -> dict:
    """
    Log shape:
    {
      "1": {
        "jamie.park@example.com": "2024-01-10T09:00:00+00:00",
        ...
      }
    }
    """
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}


def save_log(log: dict) -> None:
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def already_sent(log: dict, issue: int, email: str) -> bool:
    return str(issue) in log and email in log[str(issue)]


def record_send(log: dict, issue: int, email: str) -> None:
    key = str(issue)
    if key not in log:
        log[key] = {}
    log[key][email] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Subscriber loading
# ---------------------------------------------------------------------------

def load_subscribers() -> list[dict]:
    with open(SUBSCRIBERS_FILE, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

def generate_newsletter(
    topic: str,
    issue: int,
    subscriber: dict,
) -> tuple[str, str]:
    """
    Use OpenAI to generate a personalised newsletter for a single subscriber.
    Returns (subject, body).

    The content is anchored to the topic but framed through the lens of the
    subscriber's interests so it feels relevant to them specifically.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    system = (
        "You write engaging, concise newsletters. "
        "No fluff. Plain English. 300–400 words. "
        "Format: a short intro paragraph, 3 sections with bold headers, "
        "and a one-sentence closing."
    )

    user = f"""Write issue #{issue} of '{NEWSLETTER_NAME}' for this subscriber.

Topic: {topic}

Subscriber:
  Name: {subscriber['first_name']}
  Interests: {subscriber['interests']}

Personalise the examples and framing to match their interests.
Start with 'Hi {subscriber['first_name']},' and end with a short sign-off from {FROM_NAME}.
Return the subject on the first line as 'Subject: ...' then a blank line, then the email body."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()
    lines = raw.splitlines()

    # Parse subject from first line
    subject = f"{NEWSLETTER_NAME} — Issue #{issue}: {topic}"  # fallback
    body_start = 0

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][len("subject:"):].strip()
        body_start = 2 if len(lines) > 1 and lines[1].strip() == "" else 1

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Newsletter Agent")
    parser.add_argument("--topic", required=True, help="Newsletter topic for this issue")
    parser.add_argument("--issue", required=True, type=int, help="Issue number")
    parser.add_argument("--test-email", help="Send to this address only (for testing)")
    args = parser.parse_args()

    print(f"\n{BOLD}{NEWSLETTER_NAME} — Issue #{args.issue}{RESET}")
    print(f"Topic: {args.topic}")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    commune = CommuneClient(api_key=COMMUNE_API_KEY)
    log = load_log()
    subscribers = load_subscribers()

    # If --test-email is set, replace the subscriber list with a single entry
    if args.test_email:
        log_info(f"Test mode — sending only to {args.test_email}")
        subscribers = [{
            "first_name": "Test",
            "last_name": "Subscriber",
            "email": args.test_email,
            "interests": "general technology",
        }]

    sent_count = 0
    skipped_count = 0

    for sub in subscribers:
        email = sub["email"]

        # Skip if already sent for this issue (idempotency)
        if already_sent(log, args.issue, email) and not args.test_email:
            log_skip(f"{email} — already received issue #{args.issue}")
            skipped_count += 1
            continue

        log_info(f"Generating for {sub['first_name']} ({email}) …")

        try:
            subject, body = generate_newsletter(args.topic, args.issue, sub)
        except Exception as exc:
            print(f"  OpenAI error for {email}: {exc}", file=sys.stderr)
            continue

        try:
            commune.messages.send(
                to=email,
                subject=subject,
                text=body,
                inbox_id=COMMUNE_INBOX_ID,
                # Commune automatically adds List-Unsubscribe headers — no extra args needed
            )
        except Exception as exc:
            print(f"  Send error for {email}: {exc}", file=sys.stderr)
            continue

        record_send(log, args.issue, email)
        save_log(log)  # save after every send so partial runs are safe

        log_send(f"Sent to {email} — "{subject}"")
        sent_count += 1

        # Small delay between sends to stay within rate limits
        time.sleep(0.5)

    print(f"\n{BOLD}Done.{RESET}")
    print(f"  Sent:    {sent_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Log:     {LOG_FILE}\n")


if __name__ == "__main__":
    main()
