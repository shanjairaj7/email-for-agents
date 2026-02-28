"""
Worker Dispatch Agent — powered by Commune

Sends a personalized job dispatch SMS to every available worker in workers.json.
Each message is written by OpenAI to feel human — not a template blast.

After sending, writes job_status.json so webhook_handler.py can match
incoming replies to the right worker.

Usage:
    python dispatcher.py \\
        --job "Warehouse Packer" \\
        --date "Thursday Jan 16, 9am-5pm" \\
        --location "SF Warehouse, 123 Main St"

Environment:
    COMMUNE_API_KEY   — your Commune API key (comm_...)
    OPENAI_API_KEY    — your OpenAI API key (sk-...)
"""
import argparse
import json
import os
import time

from commune import CommuneClient
from openai import OpenAI

# ── Clients ────────────────────────────────────────────────────────────────────

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── File paths ─────────────────────────────────────────────────────────────────

WORKERS_FILE = os.path.join(os.path.dirname(__file__), "workers.json")
STATUS_FILE = os.path.join(os.path.dirname(__file__), "job_status.json")

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_workers() -> list[dict]:
    """Load worker pool from workers.json."""
    with open(WORKERS_FILE) as f:
        return json.load(f)


def get_phone_number() -> tuple[str, str]:
    """
    Return (phone_number_id, phone_number) for the first provisioned number.
    Provision a number in the Commune dashboard if this raises.
    """
    numbers = commune.phone_numbers.list()
    if not numbers:
        raise ValueError(
            "No phone numbers found. Provision one at commune.sh/dashboard."
        )
    return numbers[0].id, numbers[0].number


def personalize_sms(worker: dict, job: str, date: str, location: str) -> str:
    """
    Ask OpenAI to write a short, friendly, personalized job offer SMS.
    The prompt constrains output to 160 chars so it fits in a single SMS segment.
    """
    first_name = worker["name"].split()[0]
    skills_note = ""
    if worker.get("skills"):
        skills_note = f"Worker skills: {', '.join(worker['skills'])}. "

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a short SMS (max 160 chars) to a gig worker offering a job shift.\n\n"
                    f"Worker first name: {first_name}\n"
                    f"Job title: {job}\n"
                    f"Date/time: {date}\n"
                    f"Location: {location}\n"
                    f"{skills_note}\n"
                    f"Requirements:\n"
                    f"- Conversational, friendly tone\n"
                    f"- Use their first name\n"
                    f"- Ask them to reply YES or NO\n"
                    f"- Under 160 characters\n"
                    f"- No emojis, no markdown"
                ),
            }
        ],
    )
    return response.choices[0].message.content.strip()

# ── Main dispatch ──────────────────────────────────────────────────────────────

def dispatch_job(job: str, date: str, location: str) -> None:
    phone_id, phone_number = get_phone_number()
    workers = load_workers()
    available = [w for w in workers if w.get("status") == "available"]

    if not available:
        print("No available workers found in workers.json.")
        return

    print(f"\nDispatching: {job}")
    print(f"  Date:     {date}")
    print(f"  Location: {location}")
    print(f"  Sending to {len(available)} available workers...\n")

    job_status = {
        "job": job,
        "date": date,
        "location": location,
        "slots_required": int(os.environ.get("SLOTS_REQUIRED", "3")),
        "dispatched": [],
        "responses": {},
    }

    for worker in available:
        sms_text = personalize_sms(worker, job, date, location)

        result = commune.sms.send(
            to=worker["phone"],
            body=sms_text,
            phone_number_id=phone_id,
        )

        print(f"  SMS -> {worker['name']} ({worker['phone']})")
        print(f"         \"{sms_text}\"")

        job_status["dispatched"].append({
            "name": worker["name"],
            "phone": worker["phone"],
            "skills": worker.get("skills", []),
            "message_id": getattr(result, "message_id", None),
        })

        time.sleep(0.5)  # brief delay to stay well within rate limits

    with open(STATUS_FILE, "w") as f:
        json.dump(job_status, f, indent=2)

    print(f"\nDispatched to {len(available)} workers.")
    print(f"Status saved to job_status.json")
    print(f"\nNext step: start webhook_handler.py to capture replies.")
    print(f"  python webhook_handler.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dispatch a job to available workers via SMS."
    )
    parser.add_argument("--job", required=True, help="Job title, e.g. 'Warehouse Packer'")
    parser.add_argument(
        "--date", required=True, help="Date and time, e.g. 'Thursday Jan 16, 9am-5pm'"
    )
    parser.add_argument(
        "--location", required=True, help="Location, e.g. 'SF Warehouse, 123 Main St'"
    )
    args = parser.parse_args()
    dispatch_job(args.job, args.date, args.location)
