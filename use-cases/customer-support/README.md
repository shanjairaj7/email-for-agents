# Customer Support — Use Case Examples

Three ready-to-run examples for building AI-powered customer support with [Commune](https://commune.sh). Pick the one that fits your channel setup.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [email-support-agent/](./email-support-agent/) | Email | Python + OpenAI | Standalone email support agent with knowledge base, thread-aware replies, and spam filtering |
| [sms-support/](./sms-support/) | SMS | TypeScript + Express | Webhook-driven SMS support bot with full conversation history |
| [omnichannel-support/](./omnichannel-support/) | Email + SMS | Python + OpenAI | Single agent loop handling both email and SMS from one place |

---

## Which should I use?

```
Do you need email support?
├── Yes, email only → email-support-agent/
│
Do you need SMS support?
├── Yes, SMS only → sms-support/
│
Do you need both?
└── Yes, email + SMS → omnichannel-support/
```

**email-support-agent** — Best starting point for most teams. Includes a knowledge base, semantic search over past threads, and thread-aware replies. Zero framework dependencies — just Python and Commune.

**sms-support** — Webhook-driven TypeScript handler. Fires on every inbound SMS, loads conversation history, replies in seconds. Deploy to Railway or any Node.js host in minutes.

**omnichannel-support** — One polling loop, two channels. Customers can contact you by email or SMS — the same agent, same knowledge base, same LLM handles both. Right choice if your customers use a mix of channels.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
- SMS examples also require a Commune phone number (provision in the dashboard)
