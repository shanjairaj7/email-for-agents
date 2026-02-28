# Give Your OpenClaw Agent Its Own Phone Number

Add SMS to your OpenClaw agent in minutes using a pre-built Commune skill.

---

## What is OpenClaw?

OpenClaw is an open-source AI agent framework that runs locally on your machine. You give it tools (called skills), and it uses an LLM to decide when and how to use them. Out of the box it can browse the web, run code, and read files — but it can't send or receive SMS without a real phone number.

---

## The problem

Your OpenClaw agent can generate a message and know who to send it to — but without a phone number, it has no way to actually deliver an SMS or receive replies. Building that infrastructure from scratch means provisioning carrier numbers, handling webhooks, managing opt-outs, and storing conversation history.

---

## The solution

The `commune-sms` skill (in [`../../openclaw-email-sms/`](../../openclaw-email-sms/)) wraps the entire Commune SMS API as a set of OpenClaw-compatible tools. Install it once and your agent can send texts, read replies, search conversation history, and check who has opted out — all through natural language.

---

## Installation

**1. Install the skill**

```bash
cd ../../openclaw-email-sms
./install.sh
```

Or follow the manual setup in [`../../openclaw-email-sms/README.md`](../../openclaw-email-sms/README.md).

**2. Set environment variables**

```bash
export COMMUNE_API_KEY=comm_your_key_here
export PHONE_NUMBER_ID=pn_your_phone_number_id_here
```

**3. Restart OpenClaw**

The skill is auto-discovered on startup. You'll see `commune-sms` listed in the active tools.

---

## What to say to your agent

Once the skill is installed, talk to OpenClaw the same way you would talk to a person:

- "Send a text to +1 555 000 1234 saying 'Your appointment is confirmed for tomorrow at 2pm.'"
- "What texts have I received in the last 24 hours?"
- "Reply to the last text from Sam saying 'I'll be there by noon.'"
- "Show me all conversations where someone asked about the refund policy."
- "Which contacts have opted out of SMS?"
- "Send the shift offer to everyone in my contacts list who hasn't opted out."

The skill handles number lookup, conversation history, suppression checking, and sending — your agent just needs to describe what it wants to do.

---

## What the skill provides

| Tool | What it does |
|---|---|
| `sms_send` | Send an SMS to a phone number |
| `sms_thread` | Read the full conversation history with a contact |
| `sms_conversations` | List all active SMS threads |
| `sms_search` | Semantic search across all SMS content |
| `sms_suppressions` | Get the list of numbers that opted out |
| `phone_numbers_list` | List available Commune phone numbers |

---

## Further reading

- [openclaw-email-sms/](../../openclaw-email-sms/) — full skill documentation and SMS skill source
- [SMS capabilities reference](../../capabilities/sms/) — complete API reference for all SMS methods
- [two-way-sms/](../two-way-sms/) — if you want to build a custom SMS webhook server instead of using OpenClaw
