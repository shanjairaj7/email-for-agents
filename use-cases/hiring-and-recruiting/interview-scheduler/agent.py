"""
AI Interview Scheduler — powered by Commune

Monitors an inbox for interview scheduling requests. When one is detected, the
agent proposes available time slots, then confirms the booking when the candidate
picks one. All communication happens in the same Commune email thread.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    export INTERVIEWER_NAME="Sam Park"
    export COMPANY_NAME="Acme Inc"
    python agent.py

Environment:
    COMMUNE_API_KEY    — your Commune API key
    OPENAI_API_KEY     — your OpenAI API key
    INTERVIEWER_NAME   — name of the interviewer used in confirmation emails
    COMPANY_NAME       — company name used in confirmation emails
"""
import json
import os
import time

from dotenv import load_dotenv
from commune import CommuneClient
from openai import OpenAI

load_dotenv()

# Validate required environment variables at startup
_REQUIRED_ENV = ["COMMUNE_API_KEY", "OPENAI_API_KEY"]
for _var in _REQUIRED_ENV:
    if not os.getenv(_var):
        raise SystemExit(f"Missing required environment variable: {_var}\n"
                         f"Copy .env.example to .env and fill in your values.")

# ── Clients ────────────────────────────────────────────────────────────────────

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

INTERVIEWER_NAME = os.environ.get("INTERVIEWER_NAME", "The Hiring Team")
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Our Company")

# ── Available slots ────────────────────────────────────────────────────────────
#
# Update these with real dates and times before running.
# In production, replace this with a Google Calendar or Cal.com availability call.

AVAILABLE_SLOTS = [
    {"id": "slot_1", "label": "Monday Mar 3, 10:00am – 10:45am PST", "booked": False},
    {"id": "slot_2", "label": "Tuesday Mar 4, 2:00pm – 2:45pm PST",  "booked": False},
    {"id": "slot_3", "label": "Wednesday Mar 5, 11:00am – 11:45am PST", "booked": False},
    {"id": "slot_4", "label": "Thursday Mar 6, 3:00pm – 3:45pm PST", "booked": False},
    {"id": "slot_5", "label": "Friday Mar 7, 9:00am – 9:45am PST",   "booked": False},
]

# ── Inbox setup ────────────────────────────────────────────────────────────────

def get_inbox() -> tuple[str, str]:
    """Get or create the scheduling inbox."""
    for ib in commune.inboxes.list():
        if ib.local_part == "scheduling":
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part="scheduling")
    return ib.id, ib.address

# ── Intent classification ──────────────────────────────────────────────────────

def classify_email(subject: str, content: str) -> dict:
    """
    Classify an inbound email to determine if it's an interview request,
    a slot confirmation, or something else.

    Returns dict with keys: intent, preferred_times (str), confirmed_slot (str)
    """
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Classify this email.\n\n"
                    f"Subject: {subject}\n"
                    f"Content: {content[:800]}\n\n"
                    f"Return JSON with these fields:\n"
                    f"  intent: one of 'schedule_request', 'slot_confirmation', 'other'\n"
                    f"  preferred_times: if intent is schedule_request, extract any time preferences mentioned (e.g. 'mornings', 'Tuesday afternoon'). Empty string if none.\n"
                    f"  confirmed_slot: if intent is slot_confirmation, extract the slot they confirmed (verbatim from the email). Empty string if not applicable.\n\n"
                    f"Example: {{\"intent\": \"schedule_request\", \"preferred_times\": \"mornings next week\", \"confirmed_slot\": \"\"}}"
                ),
            }
        ],
    )
    return json.loads(response.choices[0].message.content)


# ── Slot selection ─────────────────────────────────────────────────────────────

def select_slots_to_propose(preferred_times: str, n: int = 3) -> list[dict]:
    """
    Return up to n available slots, preferring ones that match the candidate's
    stated time preference if possible.
    """
    open_slots = [s for s in AVAILABLE_SLOTS if not s["booked"]]
    if not open_slots:
        return []

    if not preferred_times:
        return open_slots[:n]

    # Ask OpenAI to rank slots by match to the preference
    slot_list = "\n".join(f"{s['id']}: {s['label']}" for s in open_slots)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Candidate prefers: \"{preferred_times}\"\n\n"
                    f"Available slots:\n{slot_list}\n\n"
                    f"Return JSON: {{\"ranked_ids\": [\"slot_id1\", \"slot_id2\", ...]}} "
                    f"ordered by best match to the preference. Include all slots."
                ),
            }
        ],
    )
    ranked = json.loads(response.choices[0].message.content).get("ranked_ids", [])
    slot_map = {s["id"]: s for s in open_slots}
    ordered = [slot_map[sid] for sid in ranked if sid in slot_map]

    # Fall back to any unranked slots at the end
    ranked_ids_set = set(ranked)
    unranked = [s for s in open_slots if s["id"] not in ranked_ids_set]
    ordered.extend(unranked)

    return ordered[:n]


# ── Email generation ───────────────────────────────────────────────────────────

def write_slot_proposal(candidate_name: str, slots: list[dict], role: str) -> str:
    """Write a friendly email proposing available interview slots."""
    slot_text = "\n".join(f"  {i+1}. {s['label']}" for i, s in enumerate(slots))

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a friendly scheduling email proposing interview slots.\n\n"
                    f"Candidate name: {candidate_name}\n"
                    f"Role: {role}\n"
                    f"Company: {COMPANY_NAME}\n"
                    f"Interviewer: {INTERVIEWER_NAME}\n"
                    f"Available slots:\n{slot_text}\n\n"
                    f"Ask the candidate to reply with their preferred option (1, 2, or 3). "
                    f"Warm professional tone. Under 120 words. No markdown."
                ),
            }
        ],
    )
    return response.choices[0].message.content.strip()


def write_confirmation(candidate_name: str, slot: dict, role: str) -> str:
    """Write a calendar-style confirmation email."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a concise interview confirmation email.\n\n"
                    f"Candidate: {candidate_name}\n"
                    f"Role: {role}\n"
                    f"Confirmed slot: {slot['label']}\n"
                    f"Interviewer: {INTERVIEWER_NAME}\n"
                    f"Company: {COMPANY_NAME}\n\n"
                    f"Include: confirmed date/time, interviewer name, a note that a calendar invite will follow. "
                    f"Warm, professional tone. Under 100 words. No markdown."
                ),
            }
        ],
    )
    return response.choices[0].message.content.strip()


def match_confirmed_slot(confirmed_text: str) -> dict | None:
    """
    Match the candidate's confirmed slot text to an available slot.
    Returns the slot dict or None.
    """
    open_slots = [s for s in AVAILABLE_SLOTS if not s["booked"]]
    if not open_slots:
        return None

    slot_list = "\n".join(f"{s['id']}: {s['label']}" for s in open_slots)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"The candidate said: \"{confirmed_text}\"\n\n"
                    f"Available slots:\n{slot_list}\n\n"
                    f"Which slot did they confirm? Return JSON: {{\"slot_id\": \"slot_X\"}} "
                    f"or {{\"slot_id\": null}} if unclear."
                ),
            }
        ],
    )
    slot_id = json.loads(response.choices[0].message.content).get("slot_id")
    if not slot_id:
        return None
    slot_map = {s["id"]: s for s in open_slots}
    return slot_map.get(slot_id)

# ── Main agent loop ────────────────────────────────────────────────────────────

def main() -> None:
    inbox_id, inbox_address = get_inbox()
    print(f"\nInterview scheduler agent")
    print(f"  Inbox:       {inbox_address}")
    print(f"  Interviewer: {INTERVIEWER_NAME} at {COMPANY_NAME}")
    print(f"  Slots available: {sum(1 for s in AVAILABLE_SLOTS if not s['booked'])}")
    print(f"\nSend an interview request email to {inbox_address} to test.")
    print("Polling every 30 seconds. Press Ctrl+C to stop.\n")

    # thread_id -> state dict
    # state keys: stage ('proposed' | 'confirmed'), proposed_slots, candidate_name, role
    thread_state: dict[str, dict] = {}

    handled_outbound: set[str] = set()

    try:
        while True:
            result = commune.threads.list(inbox_id=inbox_id, limit=20)

            for thread in result.data:
                tid = thread.thread_id

                # Skip threads where the last message was our own outbound reply
                # unless the candidate has replied again (inbound)
                if thread.last_direction == "outbound" and tid not in thread_state:
                    handled_outbound.add(tid)
                    continue

                if thread.last_direction != "inbound":
                    continue  # waiting for candidate — nothing to do

                # Load the full thread
                messages = commune.threads.messages(tid)
                last_inbound = next(
                    (m for m in reversed(messages) if m.direction == "inbound"),
                    None,
                )
                if not last_inbound:
                    continue

                content = last_inbound.content or ""
                sender = next(
                    (p.identity for p in last_inbound.participants if p.role == "sender"),
                    "there",
                )
                # Guess candidate name from email address (first part before @)
                candidate_name = sender.split("@")[0].replace(".", " ").title()

                subject = thread.subject or "Interview"

                # ── New thread: classify intent ──────────────────────────────────

                if tid not in thread_state:
                    classification = classify_email(subject, content)
                    intent = classification.get("intent", "other")

                    if intent != "schedule_request":
                        handled_outbound.add(tid)
                        continue

                    preferred = classification.get("preferred_times", "")
                    role = subject  # use email subject as the role label for simplicity

                    slots = select_slots_to_propose(preferred, n=3)
                    if not slots:
                        # No open slots — apologise and ask them to check back
                        body = (
                            f"Hi {candidate_name},\n\n"
                            f"Thank you for reaching out. Unfortunately we don't have any "
                            f"open interview slots right now. We'll follow up as soon as "
                            f"availability opens up.\n\n"
                            f"Best,\n{INTERVIEWER_NAME}"
                        )
                        commune.messages.send(
                            to=sender,
                            subject=f"Re: {subject}",
                            text=body,
                            inbox_id=inbox_id,
                            thread_id=tid,
                        )
                        handled_outbound.add(tid)
                        continue

                    body = write_slot_proposal(candidate_name, slots, role)
                    commune.messages.send(
                        to=sender,
                        subject=f"Re: {subject}",
                        text=body,
                        inbox_id=inbox_id,
                        thread_id=tid,
                    )

                    thread_state[tid] = {
                        "stage": "proposed",
                        "proposed_slots": slots,
                        "candidate_name": candidate_name,
                        "candidate_email": sender,
                        "role": role,
                    }
                    print(f"  Slots proposed -> {candidate_name} ({sender})")

                # ── Existing thread: waiting for slot confirmation ─────────────────

                elif thread_state[tid]["stage"] == "proposed":
                    state = thread_state[tid]
                    classification = classify_email(subject, content)
                    intent = classification.get("intent", "other")

                    if intent != "slot_confirmation":
                        # Not a clear confirmation — resend slots
                        slots = state["proposed_slots"]
                        body = write_slot_proposal(state["candidate_name"], slots, state["role"])
                        commune.messages.send(
                            to=state["candidate_email"],
                            subject=f"Re: {subject}",
                            text=body,
                            inbox_id=inbox_id,
                            thread_id=tid,
                        )
                        print(f"  Re-sent slots -> {state['candidate_name']}")
                        continue

                    confirmed_text = classification.get("confirmed_slot", content)
                    slot = match_confirmed_slot(confirmed_text)

                    if not slot:
                        # Couldn't match a slot — ask for clarification
                        slot_labels = "\n".join(
                            f"{i+1}. {s['label']}" for i, s in enumerate(state["proposed_slots"])
                        )
                        clarification = (
                            f"Hi {state['candidate_name']},\n\n"
                            f"Thanks for your reply! Could you confirm which slot works best by "
                            f"replying with the number?\n\n{slot_labels}\n\n"
                            f"Best,\n{INTERVIEWER_NAME}"
                        )
                        commune.messages.send(
                            to=state["candidate_email"],
                            subject=f"Re: {subject}",
                            text=clarification,
                            inbox_id=inbox_id,
                            thread_id=tid,
                        )
                        print(f"  Asked for clarification -> {state['candidate_name']}")
                        continue

                    # Mark slot as booked
                    for s in AVAILABLE_SLOTS:
                        if s["id"] == slot["id"]:
                            s["booked"] = True
                            break

                    body = write_confirmation(state["candidate_name"], slot, state["role"])
                    commune.messages.send(
                        to=state["candidate_email"],
                        subject=f"Re: {subject}",
                        text=body,
                        inbox_id=inbox_id,
                        thread_id=tid,
                    )

                    thread_state[tid]["stage"] = "confirmed"
                    print(f"  Interview confirmed -> {state['candidate_name']} | {slot['label']}")

            time.sleep(30)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")


if __name__ == "__main__":
    main()
