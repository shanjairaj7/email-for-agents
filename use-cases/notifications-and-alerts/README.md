# Notifications & Alerts — Use Case Examples

Two ready-to-run examples for building AI-powered notification systems with [Commune](https://commune.email). Both use email + SMS together.

---

## Examples

| Example | Channels | Stack | Description |
|---------|----------|-------|-------------|
| [incident-alerts/](./incident-alerts/) | Email | Python + TypeScript | AI-assessed incident alerts to on-call engineers with 10-minute escalation and acknowledgment via email reply |

---

## Which should I use?

```
Are you alerting engineers about system incidents?
└── Yes → incident-alerts/
    Sends email with full context and stack traces.
    Escalates to secondary on-call if no response in 10min.
```

---

## Why email for alerts?

Email carries context. Stack traces, runbook links, full details, reply threads — all of that lives in the thread. When an engineer (or customer) needs to take action, they read the full picture in their inbox and reply directly in thread.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.email) account and API key (`comm_...`)
- An OpenAI API key (`sk-...`)
- Python 3.11+ (for Python examples)
- Node.js 18+ (for TypeScript examples)

If you're new to Commune, start at [capabilities/quickstart/](../../capabilities/quickstart/) first.
