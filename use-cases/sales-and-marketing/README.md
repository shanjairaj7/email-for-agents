# Sales & Marketing — Use Case Examples

Three ready-to-run examples for building AI-powered sales and marketing automation with [Commune](https://commune.sh). Pick the one that fits your workflow.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [cold-outreach-sequences/](./cold-outreach-sequences/) | Email | Python + OpenAI | AI SDR agent that runs personalized multi-step outreach sequences and stops automatically on reply |
| [sms-lead-qualification/](./sms-lead-qualification/) | SMS | TypeScript + Express | Instantly texts new leads to qualify budget, timeline, and intent — emails qualified leads to your sales team |
| [newsletter-agent/](./newsletter-agent/) | Email | Python + OpenAI | Generates and sends a personalized newsletter to every subscriber, with automatic unsubscribe compliance |

---

## Which should I use?

```
Are you doing outbound prospecting?
├── Yes, multi-step email sequences → cold-outreach-sequences/
│
Are you handling inbound leads?
├── Yes, qualify them fast → sms-lead-qualification/
│
Do you want to nurture an existing list?
└── Yes, newsletters → newsletter-agent/
```

**cold-outreach-sequences** — Best starting point for outbound sales teams. Sends a personalized initial email, then follows up at day 3 and day 7 if there's no reply. Commune's `thread_id` keeps every step in a single email thread so prospects see the full conversation. Sequence halts the moment a prospect replies.

**sms-lead-qualification** — SMS has a 98% open rate. When a new lead hits your CRM or form, this agent texts them within seconds, runs a short qualification conversation (budget, timeline, decision maker), and emails a summary to your sales rep only if the lead qualifies. Built in TypeScript with Express webhooks.

**newsletter-agent** — Reads your subscriber list, generates a newsletter personalised to each subscriber's interests using OpenAI, and sends it via Commune. Commune automatically adds RFC 8058 `List-Unsubscribe` headers on every send — no extra work for CAN-SPAM or GDPR compliance.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
- SMS examples also require a Commune phone number (provision in the dashboard)
