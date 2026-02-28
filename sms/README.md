# SMS for AI Agents

Give your AI agent a real phone number. Send and receive SMS, hold multi-turn conversations, run hiring dispatches, marketing campaigns, and personal assistants — all from Python or TypeScript.

```python
from commune import CommuneClient

commune = CommuneClient(api_key="comm_...")

# Find your phone number
numbers = commune.phone_numbers.list()
phone = numbers[0]  # e.g. +14155552671

# Send a text
result = commune.sms.send(
    to="+15551234567",
    body="Your shift starts Monday at 9am. Reply YES to confirm.",
    phone_number_id=phone.id,
)
print(f"Sent — message_id={result.message_id}, credits={result.credits_charged}")
```

---

## What you can build

| Use case | What it looks like |
|---|---|
| Hiring dispatch | Text workers about open shifts, collect YES/NO confirmations |
| Personal assistant | Your own AI with a real number that texts you back |
| Marketing campaigns | Personalized outreach with drip follow-ups and response tracking |
| Alerts and monitoring | Pagerduty-style SMS alerts from any Python process |
| Customer support | Two-way AI-powered support over SMS with full conversation history |
| OpenClaw integration | Add SMS skills to your OpenClaw agent |

---

## Folder index

| Folder | Description |
|---|---|
| [quickstart/](quickstart/) | Send your first SMS in 60 seconds — Python and TypeScript |
| [agent-with-phone-number/](agent-with-phone-number/) | Flask webhook agent that reads, thinks, and replies via GPT-4o-mini |
| [hiring-agent/](hiring-agent/) | Dispatch workers, collect YES/NO confirmations, notify manager when filled |
| [personal-agent/](personal-agent/) | Your personal AI with proactive morning summaries and reactive replies |
| [sms-marketing/](sms-marketing/) | Broadcast, drip, and status campaigns with opt-out management |
| [two-way-sms/](two-way-sms/) | Minimal two-way SMS agent — best starting point for custom agents |
| [openclaw-sms/](openclaw-sms/) | Bridge doc: add SMS skills to your OpenClaw agent |
| [alert-agent/](alert-agent/) | Send SMS alerts from monitoring scripts and cron jobs |

---

## Capability reference

| Capability | Method | Notes |
|---|---|---|
| Send SMS | `commune.sms.send(to, body, phone_number_id)` | Returns `message_id`, `thread_id`, `credits_charged`, `segments` |
| Receive webhook | `POST /webhook/sms` | See payload below |
| Conversation history | `commune.sms.thread(remote_number, phone_number_id)` | Full message history, ordered oldest-first |
| Semantic search | `commune.sms.search(q, phone_number_id, limit)` | Vector search across all SMS content |
| Opt-out management | `commune.sms.suppressions(phone_number_id)` | Returns numbers that sent STOP |
| MMS | `commune.sms.send(..., media_url="https://...")` | Attach images or files |
| Auto-reply | `commune.phone_numbers.update(phone_number_id, auto_reply="...")` | Set a default auto-reply message |
| Allow / block lists | `commune.phone_numbers.update(..., allow_list=[...], block_list=[...])` | Per-number access control |

---

## How it works

When someone texts your Commune phone number, Commune posts a JSON payload to your webhook URL. Your server reads the payload, fetches conversation history, generates a reply, and sends it back — all within a few seconds.

**Inbound webhook payload:**

```python
{
    "from_number": "+15551234567",   # E.164 — the person texting you
    "to_number": "+18005551234",     # your Commune phone number
    "body": "YES, I'll take the shift",
    "message_sid": "SM...",          # carrier message ID
    "thread_id": "abc123...",        # Commune thread ID (stable across messages)
    "message": { ... },              # full UnifiedMessage object
    "num_segments": 1,               # number of 160-char SMS segments
    "credits_charged": 2             # credits consumed
}
```

Your webhook must return HTTP 200 within 10 seconds. Commune retries on failure with exponential backoff.

---

## Related

- [capabilities/sms/](../capabilities/sms/) — full API reference for all SMS methods
- [capabilities/phone-numbers/](../capabilities/phone-numbers/) — provisioning, webhooks, allow/block lists
- [use-cases/hiring-and-recruiting/](../use-cases/hiring-and-recruiting/) — end-to-end hiring workflows
- [use-cases/sales-and-marketing/](../use-cases/sales-and-marketing/) — outbound campaigns and follow-ups
- [openclaw-email-sms/](../openclaw-email-sms/) — SMS and email skills for OpenClaw agents
