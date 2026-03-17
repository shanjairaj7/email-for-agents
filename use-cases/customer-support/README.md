# Customer Support — Use Case Examples

Three ready-to-run examples for building AI-powered customer support with [Commune](https://commune.sh). Pick the one that fits your channel setup.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [email-support-agent/](./email-support-agent/) | Email | Python + OpenAI | Standalone email support agent with knowledge base, thread-aware replies, and spam filtering |
| [omnichannel-support/](./omnichannel-support/) | Email | Python + OpenAI | Single agent loop handling email from one place |

---

## Which should I use?

```
Do you need email support?
├── Yes, single-channel → email-support-agent/
│
Do you want a unified loop for your inbox?
└── Yes → omnichannel-support/
```

**email-support-agent** — Best starting point for most teams. Includes a knowledge base, semantic search over past threads, and thread-aware replies. Zero framework dependencies — just Python and Commune.

**omnichannel-support** — A polling loop for your inbox. The same agent, same knowledge base, same LLM handles all your email. Right choice if you want a single entry point for all inbound email.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
