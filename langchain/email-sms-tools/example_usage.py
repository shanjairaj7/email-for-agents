"""
Example: using commune_tools with a LangChain agent.

Demonstrates:
  1. Email-only agent — checks inbox and summarises unanswered emails
  2. SMS-only agent — sends a broadcast SMS to a list of numbers
  3. Combined email + SMS agent — escalates to SMS when an urgent email arrives

Usage:
    export COMMUNE_API_KEY=comm_...
    export OPENAI_API_KEY=sk-...
    python example_usage.py
"""
import os

from commune import CommuneClient
from commune_tools import get_email_tools, get_sms_tools
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def make_agent(tools: list, system_prompt: str) -> AgentExecutor:
    """Convenience factory: build an AgentExecutor with a system prompt."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


# ---------------------------------------------------------------------------
# Example 1: Email agent — summarise unanswered emails
# ---------------------------------------------------------------------------

def example_email_agent():
    """
    Creates an email inbox, builds email tools, and asks the agent to
    summarise any unanswered emails.
    """
    print("\n" + "=" * 60)
    print("Example 1: Email inbox summary agent")
    print("=" * 60)

    # Get or create an inbox — reuse the client to avoid extra auth calls
    inboxes = commune.inboxes.list()
    inbox = next((ib for ib in inboxes if ib.local_part == "support"), None)
    if inbox is None:
        inbox = commune.inboxes.create(local_part="support")

    # Build tools, passing the shared client
    email_tools = get_email_tools(inbox_id=inbox.id, client=commune)

    agent = make_agent(
        tools=email_tools,
        system_prompt=(
            "You are a helpful assistant with access to a Commune email inbox. "
            "When asked to summarise the inbox, use list_email_threads to see recent "
            "conversations, then identify which ones are unanswered (last_direction is "
            "'inbound'). For each unanswered thread, use get_thread_messages to read "
            "the latest message. Provide a concise summary of what each customer needs."
        ),
    )

    result = agent.invoke({
        "input": "Check the inbox and summarise any unanswered emails."
    })
    print("\nAgent output:", result["output"])


# ---------------------------------------------------------------------------
# Example 2: SMS agent — broadcast a message
# ---------------------------------------------------------------------------

def example_sms_agent():
    """
    Lists available phone numbers and sends a broadcast SMS to a list of
    recipients using the SMS tools.
    """
    print("\n" + "=" * 60)
    print("Example 2: SMS broadcast agent")
    print("=" * 60)

    # Pick the first available phone number
    numbers = commune.phone_numbers.list()
    if not numbers:
        print("No phone numbers configured on this Commune account — skipping.")
        return

    phone = numbers[0]
    sms_tools = get_sms_tools(phone_number_id=phone.id, client=commune)

    agent = make_agent(
        tools=sms_tools,
        system_prompt=(
            "You are a messaging assistant. Send SMS messages as instructed. "
            "Always use E.164 format for phone numbers. Keep messages concise."
        ),
    )

    # Send a service update broadcast to two demo numbers
    recipients = ["+14155550001", "+14155550002"]
    result = agent.invoke({
        "input": (
            f"Send the following service update SMS to each of these numbers: "
            f"{recipients}\n\n"
            f"Message: 'Scheduled maintenance is complete. All systems are operational. "
            f"Thank you for your patience.'"
        )
    })
    print("\nAgent output:", result["output"])


# ---------------------------------------------------------------------------
# Example 3: Combined email + SMS agent — urgent escalation
# ---------------------------------------------------------------------------

def example_combined_agent():
    """
    Combines email and SMS tools in a single agent. The agent reads the inbox
    and, for any email marked as urgent, both replies by email and sends an
    SMS alert to an on-call number.
    """
    print("\n" + "=" * 60)
    print("Example 3: Combined email + SMS escalation agent")
    print("=" * 60)

    # Email inbox
    inboxes = commune.inboxes.list()
    inbox = next((ib for ib in inboxes if ib.local_part == "support"), None)
    if inbox is None:
        inbox = commune.inboxes.create(local_part="support")

    # Phone number
    numbers = commune.phone_numbers.list()
    if not numbers:
        print("No phone numbers configured — skipping SMS escalation example.")
        # Fall back to email-only
        tools = get_email_tools(inbox_id=inbox.id, client=commune)
    else:
        phone = numbers[0]
        tools = (
            get_email_tools(inbox_id=inbox.id, client=commune)
            + get_sms_tools(phone_number_id=phone.id, client=commune)
        )

    ON_CALL_NUMBER = os.environ.get("ON_CALL_NUMBER", "+14155550100")

    agent = make_agent(
        tools=tools,
        system_prompt=(
            "You are an intelligent triage agent. "
            "Check the email inbox for any inbound messages that appear urgent "
            "(words like 'urgent', 'down', 'outage', 'broken', 'critical'). "
            "For urgent emails:\n"
            "  1. Reply to the sender acknowledging receipt and that the team is looking into it.\n"
            f"  2. Send an SMS alert to the on-call engineer at {ON_CALL_NUMBER} "
            "summarising the issue.\n"
            "For non-urgent emails, just acknowledge them politely by email."
        ),
    )

    result = agent.invoke({
        "input": (
            "Check the inbox for new inbound emails. "
            "Triage and respond appropriately. "
            "Escalate any urgent issues to the on-call engineer via SMS."
        )
    })
    print("\nAgent output:", result["output"])


# ---------------------------------------------------------------------------
# Run all examples
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run example 1 — always works (just needs an inbox)
    example_email_agent()

    # Run example 2 — requires at least one phone number in Commune
    example_sms_agent()

    # Run example 3 — combines both
    example_combined_agent()
