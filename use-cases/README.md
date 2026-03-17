# Use Cases — Email & SMS for AI Agents

Real-world production patterns organized by domain. Every example is standalone and runnable.

## Browse by domain

### Customer Support

| Example | Stack | Complexity |
|---------|-------|------------|
| [AI Email Support Agent](customer-support/email-support-agent/) | LangChain + Commune | Beginner |
| [Omnichannel Support](customer-support/omnichannel-support/) | Python + Commune | Advanced |

### Hiring & Recruiting

| Example | Stack | Complexity |
|---------|-------|------------|
| [Candidate Outreach Sequence](hiring-and-recruiting/candidate-email-outreach/) | Python + Commune | Intermediate |
| [Automated Interview Scheduling](hiring-and-recruiting/interview-scheduler/) | LangChain + Commune | Advanced |

### Sales & Marketing

| Example | Stack | Complexity |
|---------|-------|------------|
| [Cold Email Outreach](sales-and-marketing/cold-outreach-sequences/) | Python + Commune | Intermediate |
| [Newsletter Agent](sales-and-marketing/newsletter-agent/) | Python + Commune | Beginner |

### Notifications & Alerts

| Example | Stack | Complexity |
|---------|-------|------------|
| [Incident Alert System](notifications-and-alerts/incident-alerts/) | Python + Commune | Advanced |

### Research

| Example | Stack | Complexity |
|---------|-------|------------|
| [Email Research Agent](research/email-research-agent/) | Python + Commune | Intermediate |

## Browse by channel

**Email only**
- [AI Email Support Agent](customer-support/email-support-agent/) — AI replies to inbound support emails
- [Candidate Outreach Sequence](hiring-and-recruiting/candidate-email-outreach/) — personalized recruiter sequences
- [Cold Email Outreach](sales-and-marketing/cold-outreach-sequences/) — multi-step sales campaigns

- [Omnichannel Support](customer-support/omnichannel-support/) — unified email support agent
- [Incident Alert System](notifications-and-alerts/incident-alerts/) — email escalation with on-call alerts

## Quick start (any use case)

```python
from commune import CommuneClient

client = CommuneClient(api_key="comm_...")

# Every use case starts here
inbox = client.inboxes.create(local_part="your-agent-name")
print(f"Your agent's address: {inbox.address}")
```

## Browse by industry

**SaaS / Software**
- [customer-support/](customer-support/) — all support examples
- [research/email-research-agent/](research/email-research-agent/) — agent emails primary sources

**Staffing / HR**
- [hiring-and-recruiting/](hiring-and-recruiting/) — candidate outreach, interview scheduling

**Sales / Marketing**
- [sales-and-marketing/](sales-and-marketing/) — cold outreach, newsletter agent

**Operations**
- [notifications-and-alerts/incident-alerts/](notifications-and-alerts/incident-alerts/) — on-call escalation over email

## Related

- [Capabilities reference](../capabilities/) — deep dives on each feature
- [Framework examples](../langchain/) — framework-specific patterns
