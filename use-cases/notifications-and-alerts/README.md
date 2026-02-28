# Notifications & Alerts — Use Case Examples

Two ready-to-run examples for building AI-powered notification systems with [Commune](https://commune.email). Both use email + SMS together.

---

## Examples

| Example | Channels | Stack | Description |
|---------|----------|-------|-------------|
| [incident-alerts/](./incident-alerts/) | Email + SMS | Python + TypeScript | AI-assessed incident alerts to on-call engineers with 10-minute escalation and acknowledgment via email reply |
| [order-and-transactional-sms/](./order-and-transactional-sms/) | SMS | Python | Pattern library for AI-personalized transactional SMS — confirmations, shipping updates, delays |

---

## Which should I use?

```
Are you alerting engineers about system incidents?
└── Yes → incident-alerts/
    Sends SMS for immediate attention + email with full context.
    Escalates to secondary on-call if no response in 10min.

Are you notifying customers about order status?
└── Yes → order-and-transactional-sms/
    Drop-in functions for confirmation, shipping, delivery, and delay SMS.
    Works with any order management system.
```

---

## Why email + SMS together?

Different situations call for different channels:

**SMS** is an interrupt. People see it instantly, even away from a computer. Ideal for urgent alerts and time-sensitive order updates.

**Email** carries context. Stack traces, runbook links, full order details, reply threads — SMS can't hold all of that. Email is where the engineer (or customer) reads the full picture.

Commune gives you both channels from a single API, so your agent can use whichever is right for the moment — or both at once.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.email) account and API key (`comm_...`)
- An OpenAI API key (`sk-...`)
- Python 3.11+ (for Python examples)
- Node.js 18+ (for TypeScript examples)

If you're new to Commune, start at [capabilities/quickstart/](../../capabilities/quickstart/) first.
