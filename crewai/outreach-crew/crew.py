"""
CrewAI Lead Outreach Crew — powered by Commune

Two agents collaborate to personalise and send B2B cold outreach emails:
  1. Personalisation Agent — reads lead data, writes a tailored email
  2. Send Agent           — sends the email via Commune, records the thread_id

The thread_id returned by Commune is saved to outreach_log.json so that
follow-up sequences can reply inside the same thread later.

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python main.py
"""
import os
import json
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])


# ── Inbox setup ───────────────────────────────────────────────────────────────

def get_inbox(name: str = "outreach") -> tuple[str, str]:
    """Resolve or create the outreach inbox.

    Using a dedicated outreach inbox (separate from support) keeps reply
    tracking clean and makes it easy to search outreach history semantically.

    Returns:
        (inbox_id, inbox_address)
    """
    for ib in commune.inboxes.list():
        if ib.local_part == name:
            return ib.id, ib.address
    ib = commune.inboxes.create(local_part=name)
    return ib.id, ib.address


INBOX_ID, INBOX_ADDRESS = get_inbox()


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool("Search outreach history")
def search_outreach_history(query: str) -> str:
    """Search past outreach threads for context on similar companies or roles.

    Use this to avoid repeating messaging that didn't work, or to find
    successful subject lines and angles for similar leads.

    Args:
        query: Natural language description of what to look for,
               e.g. 'logistics company operations messaging'.

    Returns:
        JSON array of the top 3 most relevant past threads.
    """
    results = commune.search.threads(query=query, inbox_id=INBOX_ID, limit=3)
    return json.dumps(
        [{"thread_id": r.thread_id, "subject": r.subject} for r in results],
        indent=2,
    )


@tool("Send outreach email")
def send_outreach_email(to: str, subject: str, body: str) -> str:
    """Send a personalised outreach email to a lead as a new thread.

    This starts a fresh email thread. The returned thread_id is used to
    send follow-ups in the same thread later.

    Args:
        to:      Lead's email address.
        subject: Email subject line — keep it short and personalised.
        body:    Plain-text email body.

    Returns:
        JSON with status, message_id, and thread_id. Save thread_id for
        follow-up tracking.
    """
    result = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
    )
    return json.dumps(
        {
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
            "thread_id": getattr(result, "thread_id", "unknown"),
            "to": to,
        }
    )


@tool("Send follow-up email")
def send_followup_email(to: str, subject: str, body: str, thread_id: str) -> str:
    """Send a follow-up email inside an existing outreach thread.

    Use this for second or third-touch sequences. Passing thread_id ensures
    the follow-up appears as a reply in the lead's email client, preserving
    full conversation context.

    Args:
        to:        Lead's email address.
        subject:   Subject — typically "Re: <original subject>".
        body:      Plain-text follow-up body.
        thread_id: Original thread ID from the first send. REQUIRED.

    Returns:
        JSON with status and message_id.
    """
    result = commune.messages.send(
        to=to,
        subject=subject,
        text=body,
        inbox_id=INBOX_ID,
        thread_id=thread_id,
    )
    return json.dumps(
        {
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
            "thread_id": thread_id,
        }
    )


# ── Agents ────────────────────────────────────────────────────────────────────

personalizer_agent = Agent(
    role="B2B Outreach Personalisation Specialist",
    goal=(
        "Write a highly personalised, compelling cold outreach email for each "
        "lead based on their role, company context, and stated pain points."
    ),
    backstory=(
        "You are an expert B2B copywriter who specialises in cold outreach. "
        "You never write generic emails. You always anchor the message to a "
        "specific, relevant detail about the lead's company or role. You write "
        "in a direct, peer-to-peer tone — not sales-y. Your emails are short "
        "(under 120 words), open with something specific to the lead, make one "
        "clear value proposition, and end with a single low-friction ask "
        "(a 15-minute call or a simple question). You also write compelling "
        "subject lines that feel personal, not spammy."
    ),
    tools=[search_outreach_history],
    verbose=True,
)

sender_agent = Agent(
    role="Outreach Delivery Specialist",
    goal=(
        "Send the personalised email via Commune and confirm the thread_id "
        "so the sequence can be tracked and followed up correctly."
    ),
    backstory=(
        "You are responsible for the reliable delivery of outreach emails. "
        "You review the email draft to confirm it looks right, then send it "
        "using send_outreach_email. You always return the thread_id so the "
        "system can track replies and send follow-ups in the same thread."
    ),
    tools=[send_outreach_email],
    verbose=True,
)


# ── Crew factory ──────────────────────────────────────────────────────────────

def create_outreach_crew(lead: dict) -> Crew:
    """Build and return a sequential crew to handle one outreach lead.

    Args:
        lead: dict with keys: name, email, company, role, notes.

    Returns:
        A configured Crew ready for kickoff().
    """
    name = lead["name"]
    email = lead["email"]
    company = lead["company"]
    role = lead["role"]
    notes = lead["notes"]

    personalise_task = Task(
        description=f"""Write a personalised cold outreach email for this lead.

Lead details:
  Name:    {name}
  Email:   {email}
  Company: {company}
  Role:    {role}
  Notes:   {notes}

Steps:
1. Optionally call search_outreach_history with a query related to their
   industry or role to check if we have context from similar past outreach
   (e.g. what angle worked, what didn't).
2. Write a short email (under 120 words) that:
   - Opens with something specific to {name} or {company} from the notes
   - Makes one clear, relevant value proposition
   - Ends with a single low-friction ask (e.g. "Worth a 15-min chat?")
3. Write a subject line that feels personal and specific — not generic.

Output BOTH the subject line and the full email body.""",
        expected_output=(
            "subject: <the subject line>\n"
            "body: <the full email body>\n\n"
            "Both must be present. Body should be under 120 words."
        ),
        agent=personalizer_agent,
    )

    send_task = Task(
        description=f"""Review the personalised email draft and send it to the lead.

Lead:  {name} <{email}>

Steps:
1. Read the subject and body from the personalisation task output.
2. Confirm the email looks professional and specific to {name}.
3. Call send_outreach_email with:
   - to: "{email}"
   - subject: the subject from the draft
   - body: the body from the draft
4. Return the full result including thread_id.

The thread_id is critical — it will be used to send follow-ups inside
the same thread. Do not omit it from your output.""",
        expected_output=(
            "Confirmation object with status, message_id, thread_id, and to. "
            "thread_id must be present."
        ),
        agent=sender_agent,
        context=[personalise_task],
    )

    return Crew(
        agents=[personalizer_agent, sender_agent],
        tasks=[personalise_task, send_task],
        process=Process.sequential,
        verbose=True,
    )
