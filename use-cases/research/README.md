# Research — Use Case Examples

A ready-to-run example for building AI research agents that communicate via email with [Commune](https://commune.sh). The agent gets its own persistent inbox, sends questions to primary sources, collects replies, and synthesises findings into a report.

## Examples

| Example | Channel | Stack | Description |
|---------|---------|-------|-------------|
| [email-research-agent/](./email-research-agent/) | Email | Python + OpenAI | Agent with its own inbox — sends research questions, polls for replies, synthesises a markdown report |

---

## Which should I use?

This section currently has one example. It covers the core "agent with a persistent inbox" pattern — the agent holds an email address and the world can reply to it. The same pattern extends to:

- Academic outreach (emailing authors or researchers for clarifications)
- Competitive intelligence (emailing companies with product questions)
- Expert interviews (coordinating multi-source qualitative research)
- Supplier qualification (emailing vendors with spec questions)

If your use case follows any of these shapes, `email-research-agent/` is the right starting point.

---

## Prerequisites

All examples require:

- A [Commune](https://commune.sh) account and API key (`comm_...`)
- An [OpenAI](https://platform.openai.com) API key (`sk-...`)
