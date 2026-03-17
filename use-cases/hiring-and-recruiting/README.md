# Hiring & Recruiting — AI Agent Use Cases

Three ready-to-run examples for building AI-powered hiring and recruiting workflows with [Commune](https://commune.sh). Each one is self-contained and production-ready.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [candidate-email-outreach/](./candidate-email-outreach/) | Email | Python + OpenAI | AI recruiter reads a candidate list, sends personalized outreach emails, monitors for replies, and continues the conversation in-thread |
| [interview-scheduler/](./interview-scheduler/) | Email | Python + OpenAI | Agent monitors an inbox for interview requests, proposes available time slots, and sends confirmation emails — all within a single email thread |

---

## Which should I use?

```
Are you doing candidate sourcing or outreach at scale?
└── Yes → candidate-email-outreach/
    Reads a CSV, personalizes every email with LLM, tracks replies per thread.

Do you need to automate the back-and-forth of interview scheduling?
└── Yes → interview-scheduler/
    Monitors inbox, proposes time slots, confirms bookings in the same thread.
```

**candidate-email-outreach** — Best for teams doing sourcing at volume. A polling agent that reads a CSV, writes a personalized email per candidate with OpenAI, tracks every reply by `thread_id`, and continues the conversation automatically. No separate database needed — Commune's threading keeps everything organized.

**interview-scheduler** — A focused, single-purpose agent. Monitors an inbox for scheduling requests, parses availability from the email, proposes slots, and sends calendar-ready confirmations. All replies stay in the same email thread with a single `thread_id`.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
