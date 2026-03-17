# Quickstart — Give Your Agent an Email Address

```python
# Install
pip install commune-mail

# Give your agent an email address in 3 lines
from commune import CommuneClient
commune = CommuneClient(api_key="comm_...")
inbox = commune.inboxes.create(local_part="my-agent")
print(inbox.address)  # → my-agent@yourdomain.commune.email
```

```typescript
// TypeScript
// npm install commune-ai
import { CommuneClient } from 'commune-ai';
const commune = new CommuneClient({ apiKey: 'comm_...' });
const inbox = await commune.inboxes.create({ localPart: 'my-agent' });
console.log(inbox.address); // → my-agent@yourdomain.commune.email
```

That's it. Your agent has an inbox. Get your API key at [commune.email](https://commune.email).

---

## What can your agent do with this inbox?

- **Send emails** — outbound messages from your agent's address, with thread awareness
- **Receive emails** — Commune delivers inbound mail to your webhook endpoint in real time
- **Search past threads** — retrieve any conversation by thread ID, list all threads in an inbox
- **Extract structured data** — configure a JSON schema once; Commune populates it from every inbound email automatically, before your webhook fires
- **Get delivery metrics** — sent, delivered, bounced, opened — available per message

---

## Send your first email

```python
result = commune.messages.send(
    to="you@example.com",
    subject="Hello from my agent",
    text="This email was sent by an AI agent using Commune.",
    inbox_id=inbox.id,
)
print(result.thread_id)  # save this for replies
```

```typescript
const result = await commune.messages.send({
  to: 'you@example.com',
  subject: 'Hello from my agent',
  text: 'This email was sent by an AI agent using Commune.',
  inboxId: inbox.id,
});
console.log(result.thread_id);
```

---

## Files in this directory

| File | What it does |
|------|-------------|
| `give-your-agent-email.py` | Create inbox, print address, send test email |
| `send-your-first-email.py` | Minimal example: create inbox → send email |
| `setup.py` | Onboarding: inbox + test email |

---

## Next steps

Once you have an inbox, you're ready for the real use cases:

- **[use-cases/customer-support/](../../use-cases/customer-support/)** — email + SMS support agent with knowledge base and thread-aware replies
- **[use-cases/notifications-and-alerts/](../../use-cases/notifications-and-alerts/)** — incident alerting with SMS escalation and email acknowledgment
- **[mcp-server/](../../mcp-server/)** — give Claude Desktop or any MCP client a live email inbox
- **[capabilities/email-threading/](../email-threading/)** — keep all replies in one thread
- **[capabilities/structured-extraction/](../structured-extraction/)** — auto-parse inbound emails into JSON

```mermaid
flowchart LR
    A[Get API key] --> B[Create inbox]
    B --> C[Send email]
    C --> F[Build your use case]
    F --> G[customer-support/]
    F --> H[notifications-and-alerts/]
    F --> I[mcp-server/]
```
