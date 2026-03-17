# Sales & Marketing — Use Case Examples

Three ready-to-run examples for building AI-powered sales and marketing automation with [Commune](https://commune.sh). Pick the one that fits your workflow.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [cold-outreach-sequences/](./cold-outreach-sequences/) | Email | Python + OpenAI | AI SDR agent that runs personalized multi-step outreach sequences and stops automatically on reply |
| [newsletter-agent/](./newsletter-agent/) | Email | Python + OpenAI | Generates and sends a personalized newsletter to every subscriber, with automatic unsubscribe compliance |

---

## Which should I use?

```
Are you doing outbound prospecting?
├── Yes, multi-step email sequences → cold-outreach-sequences/
│
Do you want to nurture an existing list?
└── Yes, newsletters → newsletter-agent/
```

**cold-outreach-sequences** — Best starting point for outbound sales teams. Sends a personalized initial email, then follows up at day 3 and day 7 if there's no reply. Commune's `thread_id` keeps every step in a single email thread so prospects see the full conversation. Sequence halts the moment a prospect replies.

**newsletter-agent** — Reads your subscriber list, generates a newsletter personalised to each subscriber's interests using OpenAI, and sends it via Commune. Commune automatically adds RFC 8058 `List-Unsubscribe` headers on every send — no extra work for CAN-SPAM or GDPR compliance.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
