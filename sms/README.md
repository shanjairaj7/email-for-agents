# SMS Examples

Give your AI agent a real phone number. Two-way SMS with semantic search across messages and email in a single unified index.

---

## Examples

| Example | Description |
|---------|-------------|
| [Provision & Send](provision_send/) | Provision a number and send your first SMS in under 60 seconds |
| [Two-Way Conversation](two_way/) | Agent receives inbound SMS via webhook and replies intelligently |
| [Escalation from Email](escalation/) | Agent escalates from an email thread to SMS when urgency is high |
| [Unified Search](unified_search/) | Semantic search across SMS and email in a single query |

---

## Install

```bash
# Python
pip install commune-mail python-dotenv

# TypeScript
npm install commune-ai
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
```

---

## Provision and send — Python

```python
import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

# Provision a real phone number
phone = commune.phone_numbers.provision()
print(f"Phone number provisioned: {phone.number}")
# → +14155552671

# Send an SMS
message = commune.sms.send(
    to="+14155551234",
    body="Your order has shipped and will arrive tomorrow.",
    phone_number_id=phone.id,
)
print(f"SMS sent. Message ID: {message.id}")
```

---

## Provision and send — TypeScript

```typescript
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function main(): Promise<void> {
    // Provision a real phone number
    const phone = await commune.phoneNumbers.provision();
    console.log(`Phone number provisioned: ${phone.number}`);
    // → +14155552671

    // Send an SMS
    const message = await commune.sms.send({
        to: '+14155551234',
        body: 'Your order has shipped and will arrive tomorrow.',
        phoneNumberId: phone.id,
    });
    console.log(`SMS sent. Message ID: ${message.id}`);
}

main().catch(console.error);
```

---

## Two-way SMS via webhook

Inbound SMS fires a `sms.received` webhook event. Handle it the same way as `message.received` for email:

```typescript
import express from 'express';
import { verifyCommuneWebhook, CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const app = express();

app.post('/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const event = verifyCommuneWebhook(
        req.body,
        req.headers['commune-signature'] as string,
        process.env.COMMUNE_WEBHOOK_SECRET!,
    );

    res.sendStatus(200);

    if (event.type === 'sms.received') {
        const { from_number, body, phone_number_id } = event.data;
        console.log(`Inbound SMS from ${from_number}: ${body}`);

        // Search past conversations for context (SMS + email unified)
        const context = await commune.search.threads({
            query: body,
            limit: 3,
        });

        // Generate and send a reply
        const reply = await generateReply(body, context);
        await commune.sms.send({
            to: from_number,
            body: reply,
            phoneNumberId: phone_number_id,
        });
    }
});

async function generateReply(message: string, context: any[]): Promise<string> {
    // Call your LLM here with the message and context
    return 'Thanks for your message — we will follow up shortly.';
}

app.listen(3000);
```

---

## Escalation from email to SMS — Python

When a support thread is flagged as high urgency, your agent can escalate to SMS:

```python
import os
from commune import CommuneClient

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])

def escalate_to_sms(thread_id: str, customer_phone: str, issue_summary: str) -> str:
    """
    Escalate a high-urgency email thread to SMS.
    Call this when email response time is not acceptable.
    """
    phone_number_id = os.environ["COMMUNE_PHONE_NUMBER_ID"]

    msg = commune.sms.send(
        to=customer_phone,
        body=(
            f"Hi, this is the support team. We've seen your request "
            f"re: {issue_summary[:80]} and are handling it urgently. "
            f"We'll have a resolution within the hour."
        ),
        phone_number_id=phone_number_id,
    )

    # Mark the email thread as escalated
    commune.threads.set_status(thread_id, "escalated")

    return f"Escalation SMS sent to {customer_phone}. Message ID: {msg.id}"
```

---

## Unified search across SMS and email

SMS messages and emails are stored in the same vector index. One query searches both:

```python
results = commune.search.threads(
    query="customer asking about refund",
    limit=5,
    # No inbox_id filter = searches SMS and email together
)

for result in results:
    print(f"[{result.channel}] score={result.score:.2f} — {result.subject or result.snippet}")
    # [email] score=0.94 — Re: Order #1234 damaged
    # [sms]   score=0.87 — "i want my money back"
    # [email] score=0.81 — Refund request for order #5678
```

This means your agent has complete context about a customer across every channel — without querying SMS and email separately.

---

## Tips

- Provision phone numbers programmatically — one number per agent or one shared number is both valid patterns
- Phone numbers are persistent — provision once, store the `phone_number_id`, reuse it
- Use `idempotency_key` on `sms.send()` for the same deduplication guarantees as email
- Inbound SMS fires `sms.received` — the same webhook endpoint can handle both `message.received` and `sms.received`
- The unified search index means you never need to maintain separate context stores for SMS vs email

---

[Back to main README](../README.md)
