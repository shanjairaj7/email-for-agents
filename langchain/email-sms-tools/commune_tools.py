"""
Reusable LangChain tools for Commune Email & SMS API.

Drop these into any LangChain agent:
    from commune_tools import get_email_tools, get_sms_tools

Example:
    tools = get_email_tools(inbox_id="your_inbox_id")
    # → [list_email_threads, get_thread_messages, send_email, reply_to_thread, search_emails]

    sms_tools = get_sms_tools(phone_number_id="your_phone_number_id")
    # → [send_sms, list_sms_conversations, get_sms_thread]

Both factory functions accept an optional `client` argument so you can share a
single CommuneClient instance across tool groups (avoids duplicate auth).
"""
import json
import os
from typing import Optional

from commune import CommuneClient
from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Email tools
# ---------------------------------------------------------------------------

def get_email_tools(
    inbox_id: str,
    client: Optional[CommuneClient] = None,
) -> list:
    """
    Return a list of LangChain tools for Commune email operations.

    Args:
        inbox_id:  The Commune inbox ID to operate on.
        client:    Optional pre-constructed CommuneClient. If omitted, one is
                   created from the COMMUNE_API_KEY environment variable.

    Returns:
        List of LangChain tool callables:
        [list_email_threads, get_thread_messages, send_email,
         reply_to_thread, search_emails]
    """
    comm = client or CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

    # ------------------------------------------------------------------
    # Each tool is defined as a closure so it captures `comm` and
    # `inbox_id` without global state. The @tool decorator is applied
    # inside the factory function — LangChain picks up the docstring
    # for the tool description that the LLM sees.
    # ------------------------------------------------------------------

    @tool
    def list_email_threads(limit: int = 20) -> str:
        """
        List recent email threads in the inbox.
        Returns a JSON array with thread_id, subject, last_direction
        ('inbound'/'outbound'), and message_count.

        Use this first to discover what conversations exist before
        reading a specific thread.

        Args:
            limit: Maximum number of threads to return (default 20).
        """
        result = comm.threads.list(inbox_id=inbox_id, limit=limit)
        threads = [
            {
                "thread_id": t.thread_id,
                "subject": t.subject,
                "last_direction": t.last_direction,
                "message_count": t.message_count,
                "last_message_at": str(t.last_message_at),
            }
            for t in result.data
        ]
        return json.dumps(threads, indent=2)

    @tool
    def get_thread_messages(thread_id: str) -> str:
        """
        Fetch all messages in an email thread.
        Returns a JSON array with direction ('inbound'/'outbound'),
        sender address, content, and created_at timestamp.

        Use this to read the full conversation before replying.

        Args:
            thread_id: The thread ID from list_email_threads.
        """
        messages = comm.threads.messages(thread_id)
        return json.dumps(
            [
                {
                    "direction": m.direction,
                    "sender": next(
                        (p.identity for p in m.participants if p.role == "sender"),
                        "unknown",
                    ),
                    "content": m.content,
                    "created_at": str(m.created_at),
                }
                for m in messages
            ],
            indent=2,
        )

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """
        Send a new email, starting a fresh thread.
        Returns JSON with status and message_id.

        Use reply_to_thread instead if you are responding to an existing
        conversation — that keeps messages in the same thread for the recipient.

        Args:
            to:      Recipient email address.
            subject: Email subject line.
            body:    Plain-text email body.
        """
        result = comm.messages.send(
            to=to,
            subject=subject,
            text=body,
            inbox_id=inbox_id,
        )
        return json.dumps({
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
        })

    @tool
    def reply_to_thread(thread_id: str, to: str, subject: str, body: str) -> str:
        """
        Send a reply within an existing email thread.
        Always prefer this over send_email when responding to a conversation —
        it keeps the reply in the same thread so the recipient sees the history.

        Args:
            thread_id: The thread ID to reply in (from list_email_threads).
            to:        Recipient email address.
            subject:   Reply subject (usually 'Re: <original subject>').
            body:      Plain-text reply body.
        """
        result = comm.messages.send(
            to=to,
            subject=subject,
            text=body,
            inbox_id=inbox_id,
            thread_id=thread_id,
        )
        return json.dumps({
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
        })

    @tool
    def search_emails(query: str) -> str:
        """
        Semantic search across all email threads in the inbox.
        Returns the top matching threads with thread_id, subject, and
        a relevance score (0–1).

        Use natural language queries — e.g. "billing refund request" or
        "password reset help".

        Args:
            query: Natural language search query.
        """
        results = comm.search.threads(query=query, inbox_id=inbox_id, limit=5)
        if not results:
            return json.dumps({"message": "No matching threads found."})
        return json.dumps(
            [
                {
                    "thread_id": r.thread_id,
                    "subject": r.subject,
                    "score": round(r.score, 3),
                }
                for r in results
            ],
            indent=2,
        )

    return [
        list_email_threads,
        get_thread_messages,
        send_email,
        reply_to_thread,
        search_emails,
    ]


# ---------------------------------------------------------------------------
# SMS tools
# ---------------------------------------------------------------------------

def get_sms_tools(
    phone_number_id: str,
    client: Optional[CommuneClient] = None,
) -> list:
    """
    Return a list of LangChain tools for Commune SMS operations.

    Args:
        phone_number_id: The Commune phone number ID to send from.
        client:          Optional pre-constructed CommuneClient.

    Returns:
        List of LangChain tool callables:
        [send_sms, list_sms_conversations, get_sms_thread]
    """
    comm = client or CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

    @tool
    def send_sms(to: str, message: str) -> str:
        """
        Send an SMS message to a phone number.
        Returns JSON with status and message_id.

        Args:
            to:      Recipient phone number in E.164 format (e.g. +14155551234).
                     Always include the country code and leading '+'.
            message: The text message content. Keep under 160 chars for a
                     single SMS segment; longer messages are split automatically.
        """
        result = comm.sms.send(
            to=to,
            body=message,
            phone_number_id=phone_number_id,
        )
        return json.dumps({
            "status": "sent",
            "message_id": getattr(result, "message_id", "ok"),
        })

    @tool
    def list_sms_conversations() -> str:
        """
        List all active SMS conversations on this phone number.
        Returns JSON array with thread_id, remote_number, message_count,
        and a preview of the last message.

        Use this to discover what conversations exist before reading a
        specific thread.
        """
        conversations = comm.sms.conversations(phone_number_id=phone_number_id)
        return json.dumps(
            [
                {
                    "thread_id": c.thread_id,
                    "remote_number": c.remote_number,
                    "message_count": c.message_count,
                    "last_message": getattr(c, "last_message_preview", ""),
                }
                for c in conversations
            ],
            indent=2,
        )

    @tool
    def get_sms_thread(remote_number: str) -> str:
        """
        Get the full SMS message history with a specific phone number.
        Returns a JSON array with direction ('inbound'/'outbound'),
        content, and created_at timestamp.

        Args:
            remote_number: The remote phone number in E.164 format (+14155551234).
                           Use list_sms_conversations to discover numbers.
        """
        messages = comm.sms.thread(
            remote_number=remote_number,
            phone_number_id=phone_number_id,
        )
        return json.dumps(
            [
                {
                    "direction": m.direction,
                    "content": m.content,
                    "created_at": str(m.created_at),
                }
                for m in messages
            ],
            indent=2,
        )

    return [send_sms, list_sms_conversations, get_sms_thread]
