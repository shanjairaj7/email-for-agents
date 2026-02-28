"""
Hiring agent: dispatch open shifts via SMS and collect YES/NO confirmations.

Two modes:
  python agent.py dispatch   — send shift offer SMS to all eligible workers in shifts.json
  python agent.py webhook    — start Flask server to receive and process worker replies

State is persisted in shift_status.json so the webhook server can restart without
losing track of who has confirmed.
"""

import os
import sys
import json
import time
from flask import Flask, request, jsonify
from commune import CommuneClient
from dotenv import load_dotenv

load_dotenv()

# Validate required environment variables at startup.
required_vars = ["COMMUNE_API_KEY", "PHONE_NUMBER_ID", "COMMUNE_INBOX_ID", "MANAGER_EMAIL"]
for var in required_vars:
    if not os.environ.get(var):
        raise SystemExit(f"Missing env var: {var} — copy .env.example to .env and fill it in.")

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
COMMUNE_INBOX_ID = os.environ["COMMUNE_INBOX_ID"]
MANAGER_EMAIL = os.environ["MANAGER_EMAIL"]

# How many confirmed workers are needed before we notify the manager.
REQUIRED_CONFIRMATIONS = int(os.environ.get("REQUIRED_CONFIRMATIONS", "1"))

SHIFTS_FILE = os.path.join(os.path.dirname(__file__), "shifts.json")
STATUS_FILE = os.path.join(os.path.dirname(__file__), "shift_status.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_status() -> dict:
    """Load current shift confirmation state from disk, or return empty dict."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"[warn] Could not read status file: {e}")
            return {}
    return {}


def save_status(status: dict) -> None:
    """Persist shift confirmation state to disk."""
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)


def notify_manager(confirmed_workers: list) -> None:
    """
    Send the manager a summary email when all required shifts are filled.
    Uses Commune email (commune.messages.send) so the hiring loop is fully handled
    by the same Commune account — no separate email provider needed.
    """
    worker_list = "\n".join(f"  - {w}" for w in confirmed_workers)
    try:
        commune.messages.send(
            to=MANAGER_EMAIL,
            subject=f"All {len(confirmed_workers)} shifts confirmed!",
            text=(
                f"All required shifts are now filled.\n\n"
                f"Confirmed workers:\n{worker_list}\n\n"
                f"No further action needed."
            ),
            inbox_id=COMMUNE_INBOX_ID,
        )
        print(f"[email] Manager notified at {MANAGER_EMAIL}")
    except Exception as e:
        print(f"[warn] Could not send manager email: {e}")


# ---------------------------------------------------------------------------
# Dispatch mode: send shift offers to workers
# ---------------------------------------------------------------------------

def dispatch_shifts() -> None:
    """
    Read shifts.json, check opt-out list, and send personalized SMS to each worker.
    Skips workers who have opted out via STOP (suppressions list).
    """
    with open(SHIFTS_FILE) as f:
        shifts = json.load(f)

    # Fetch the current opt-out list. Commune tracks STOP replies automatically.
    # We check this before every send rather than caching it — the list can change.
    suppressed_raw = commune.sms.suppressions(phone_number_id=PHONE_NUMBER_ID)
    suppressed = {s.phone_number for s in suppressed_raw}
    print(f"Suppression list: {len(suppressed)} numbers opted out")

    sent = 0
    skipped = 0

    for shift in shifts:
        shift_desc = (
            f"{shift['role']} on {shift['date']} at {shift['location']}"
        )
        for worker in shift.get("workers", []):
            name = worker.get("name", "there")
            phone = worker.get("phone", "")

            if not phone:
                print(f"  SKIP {name} — no phone number")
                continue

            if phone in suppressed:
                print(f"  SKIP {name} ({phone}) — opted out")
                skipped += 1
                continue

            msg = (
                f"Hi {name}! Shift available: {shift_desc}. "
                f"Reply YES to confirm or NO to decline."
            )

            try:
                result = commune.sms.send(
                    to=phone,
                    body=msg,
                    phone_number_id=PHONE_NUMBER_ID,
                )
                print(f"  SENT to {name} ({phone}): {result.message_id}")
                sent += 1
            except Exception as e:
                print(f"  FAIL {name} ({phone}): {e}")

            # Respect carrier rate limits — don't blast too fast
            time.sleep(0.5)

    print(f"\nDispatch complete. Sent: {sent}, Skipped (opted out): {skipped}")
    print(f"Run 'python agent.py webhook' to receive replies.")


# ---------------------------------------------------------------------------
# Webhook mode: receive and process worker replies
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/webhook/sms", methods=["POST"])
def handle_reply():
    """
    Process inbound SMS replies from workers.

    Workers reply YES or NO. Anything else gets a clarification prompt.
    After each reply, we check if all required confirmations have been received
    and notify the manager if so.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    from_number: str = data.get("from_number", "")
    body: str = data.get("body", "").strip().upper()

    if not from_number:
        return jsonify({"error": "Missing from_number"}), 400

    status = load_status()
    already_notified = status.get("__manager_notified", False)

    if body.startswith("YES"):
        status[from_number] = "confirmed"
        try:
            commune.sms.send(
                to=from_number,
                body="Great! You're confirmed. We'll send details shortly.",
                phone_number_id=PHONE_NUMBER_ID,
            )
        except Exception as e:
            print(f"[warn] Could not send confirmation to {from_number}: {e}")
        print(f"[reply] {from_number} → CONFIRMED")

    elif body.startswith("NO"):
        status[from_number] = "declined"
        try:
            commune.sms.send(
                to=from_number,
                body="No problem! We'll reach out if another shift opens up.",
                phone_number_id=PHONE_NUMBER_ID,
            )
        except Exception as e:
            print(f"[warn] Could not send decline ack to {from_number}: {e}")
        print(f"[reply] {from_number} → DECLINED")

    else:
        # Ambiguous reply — ask them to clarify
        try:
            commune.sms.send(
                to=from_number,
                body="Please reply YES to confirm or NO to decline the shift.",
                phone_number_id=PHONE_NUMBER_ID,
            )
        except Exception as e:
            print(f"[warn] Could not send clarification to {from_number}: {e}")
        print(f"[reply] {from_number} → AMBIGUOUS: '{body[:40]}'")

    save_status(status)

    # Check if we've hit the required confirmation threshold
    confirmed = [num for num, s in status.items() if s == "confirmed" and not num.startswith("__")]
    print(f"  Confirmed so far: {len(confirmed)}/{REQUIRED_CONFIRMATIONS}")

    if len(confirmed) >= REQUIRED_CONFIRMATIONS and not already_notified:
        notify_manager(confirmed)
        status["__manager_notified"] = True
        save_status(status)

    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"

    if mode == "dispatch":
        try:
            dispatch_shifts()
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)

    elif mode == "webhook":
        print(f"Webhook server starting on port 8000. POST /webhook/sms")
        print(f"Required confirmations: {REQUIRED_CONFIRMATIONS}")
        try:
            app.run(port=8000, debug=False)
        except KeyboardInterrupt:
            print("\nShutting down.")
            sys.exit(0)

    else:
        print("Usage:")
        print("  python agent.py dispatch   — send shift offer SMS to workers")
        print("  python agent.py webhook    — start server to receive replies")
        sys.exit(1)
