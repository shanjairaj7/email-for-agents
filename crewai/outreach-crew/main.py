"""
Main entry point — reads leads from leads.csv, skips already-contacted leads,
runs the outreach crew per lead, and saves thread_ids to outreach_log.json
for follow-up sequence tracking.

Run:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python main.py

The script is safe to re-run: already-contacted emails are skipped by
checking outreach_log.json before sending.
"""
import csv
import json
import os
import time
from pathlib import Path

from crew import INBOX_ADDRESS, create_outreach_crew

# Paths
LEADS_FILE = Path(__file__).parent / "leads.csv"
LOG_FILE = Path(__file__).parent / "outreach_log.json"

# Delay between sends (seconds) — avoids triggering spam filters.
SEND_DELAY_SECONDS = 5


def load_log() -> dict:
    """Load the outreach log from disk.

    The log is a dict keyed by email address:
    {
        "alice@example.com": {
            "name": "Alice",
            "company": "Acme",
            "thread_id": "thrd_abc123",
            "sent_at": "2024-01-15T10:30:00",
            "status": "sent"
        },
        ...
    }
    """
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}


def save_log(log: dict) -> None:
    """Persist the outreach log to disk."""
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)
    print(f"Log saved to {LOG_FILE}")


def load_leads() -> list[dict]:
    """Read leads from leads.csv and return as a list of dicts."""
    with open(LEADS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def extract_thread_id(crew_result: str) -> str:
    """Attempt to extract thread_id from the crew's final output string.

    The Send Agent is instructed to include thread_id in its output. This
    function tries to parse it from JSON in the result; falls back to 'unknown'.
    """
    result_str = str(crew_result)
    # Try to find a JSON object containing thread_id in the result string.
    start = result_str.find("{")
    end = result_str.rfind("}") + 1
    if start != -1 and end > start:
        try:
            data = json.loads(result_str[start:end])
            if "thread_id" in data:
                return data["thread_id"]
        except json.JSONDecodeError:
            pass
    return "unknown"


def main() -> None:
    leads = load_leads()
    log = load_log()

    already_contacted = set(log.keys())
    pending = [lead for lead in leads if lead["email"] not in already_contacted]

    print(f"Commune Outreach Crew | sending from: {INBOX_ADDRESS}")
    print(f"Total leads: {len(leads)} | Already contacted: {len(already_contacted)} | Pending: {len(pending)}\n")

    if not pending:
        print("All leads have been contacted. Add new leads to leads.csv to continue.")
        return

    for lead in pending:
        name = lead["name"]
        email = lead["email"]
        company = lead["company"]

        print(f"Processing: {name} <{email}> at {company}")

        try:
            crew = create_outreach_crew(lead)
            result = crew.kickoff()

            thread_id = extract_thread_id(result)

            # Record in log.
            log[email] = {
                "name": name,
                "company": company,
                "role": lead["role"],
                "thread_id": thread_id,
                "sent_at": __import__("datetime").datetime.utcnow().isoformat(),
                "status": "sent",
            }
            save_log(log)

            print(f"Sent to {name} | thread_id: {thread_id}\n")

        except Exception as exc:
            print(f"[error] Failed for {name} <{email}>: {exc}")
            log[email] = {
                "name": name,
                "company": company,
                "role": lead["role"],
                "thread_id": None,
                "sent_at": __import__("datetime").datetime.utcnow().isoformat(),
                "status": f"error: {exc}",
            }
            save_log(log)

        # Brief pause between sends.
        if pending.index(lead) < len(pending) - 1:
            print(f"Waiting {SEND_DELAY_SECONDS}s before next send...")
            time.sleep(SEND_DELAY_SECONDS)

    print("\nOutreach complete.")
    contacted_count = sum(1 for v in log.values() if v.get("status") == "sent")
    print(f"Successfully contacted: {contacted_count}/{len(leads)} leads")
    print(f"Thread IDs saved to: {LOG_FILE}")
    print("\nTo send follow-ups, re-use the thread_id from outreach_log.json with commune.messages.send(..., thread_id=thread_id).")


if __name__ == "__main__":
    main()
