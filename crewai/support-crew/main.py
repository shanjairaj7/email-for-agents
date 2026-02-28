"""
Main entry point — polls the Commune inbox every 30 seconds and runs the
CrewAI support crew for every unanswered inbound email thread.

Run:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python main.py
"""
import time

from crew import commune, INBOX_ID, INBOX_ADDRESS, create_support_crew


def main() -> None:
    # Track thread IDs already handled in this session so we never reply twice.
    handled: set[str] = set()

    print(f"CrewAI Support Crew running | inbox: {INBOX_ADDRESS}")
    print("Polling every 30 seconds. Send an email to the inbox address to test.\n")

    while True:
        try:
            result = commune.threads.list(inbox_id=INBOX_ID, limit=20)
        except Exception as exc:
            print(f"[warn] Failed to list threads: {exc}. Retrying in 30s.")
            time.sleep(30)
            continue

        for thread in result.data:
            # Skip threads we've already handled, or threads where the last
            # message is outbound (i.e. we sent it — no reply needed).
            if thread.thread_id in handled:
                continue
            if thread.last_direction == "outbound":
                handled.add(thread.thread_id)
                continue

            subject = thread.subject or "(no subject)"
            print(f"\nNew inbound thread: [{thread.thread_id}] {subject}")

            thread_info = {
                "thread_id": thread.thread_id,
                "subject": subject,
            }

            try:
                crew = create_support_crew(thread_info)
                crew_result = crew.kickoff()
                print(f"Crew finished for thread {thread.thread_id}: {crew_result}")
            except Exception as exc:
                print(f"[error] Crew failed for thread {thread.thread_id}: {exc}")
            finally:
                # Mark as handled regardless of success to avoid infinite retries.
                handled.add(thread.thread_id)

        time.sleep(30)


if __name__ == "__main__":
    main()
