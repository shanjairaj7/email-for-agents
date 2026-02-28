# TypeScript Email & SMS Examples

Full end-to-end TypeScript examples: HMAC-verified webhook handlers, multi-agent coordination with typed thread payloads, SMS flows, and customer support agents — all typed against the `commune-ai` SDK.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support Agent](customer_support/) | Express webhook handler reads inbound, calls OpenAI, sends reply |
| [Multi-Agent Coordination](multi_agent/) | Two agents hand off tasks over email with typed thread payloads |
| [SMS Notifications](sms/) | Provision a number, send SMS, handle inbound replies via webhook |
| [Webhook Handler](webhook/) | Reference implementation with `verifyCommuneWebhook` and retry-safe handling |

---

## Install

```bash
npm install commune-ai
# For the webhook examples:
npm install express @types/express
```

## Configure

```bash
export COMMUNE_API_KEY=comm_...
export COMMUNE_WEBHOOK_SECRET=whsec_...
export COMMUNE_INBOX_ID=inbox_...
```

---

## Webhook handler — reference implementation

This is the most important pattern. Every Commune integration eventually needs a webhook handler. This implementation is retry-safe, HMAC-verified, and handles all event types.

```typescript
import express, { Request, Response } from 'express';
import { CommuneClient, verifyCommuneWebhook, CommuneWebhookEvent } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const app = express();

// IMPORTANT: Use express.raw() — not express.json() — for webhook routes.
// HMAC verification requires the raw request body, not the parsed JSON.
app.post(
    '/webhook/commune',
    express.raw({ type: 'application/json' }),
    async (req: Request, res: Response) => {
        // 1. Verify the signature — reject anything that fails
        let event: CommuneWebhookEvent;
        try {
            event = verifyCommuneWebhook(
                req.body,
                req.headers['commune-signature'] as string,
                process.env.COMMUNE_WEBHOOK_SECRET!,
            );
        } catch (err) {
            console.error('Webhook signature verification failed:', err);
            return res.status(400).json({ error: 'Invalid signature' });
        }

        // 2. Acknowledge immediately — Commune retries if it doesn't get 200 within 10s
        res.sendStatus(200);

        // 3. Process the event asynchronously
        setImmediate(() => handleEvent(event).catch(console.error));
    }
);

async function handleEvent(event: CommuneWebhookEvent): Promise<void> {
    console.log(`Handling event: ${event.type} (id=${event.id})`);

    switch (event.type) {
        case 'message.received': {
            const { thread_id, from_address, text, inbox_id } = event.data;

            // Get the full thread for context
            const messages = await commune.threads.messages(thread_id);
            const history = messages
                .map(m => `${m.from_address}: ${m.text}`)
                .join('\n\n');

            // Search for similar past cases
            const similar = await commune.search.threads({
                query: text,
                inboxId: inbox_id,
                limit: 3,
            });

            console.log(`New message from ${from_address} in thread ${thread_id}`);
            console.log(`Found ${similar.length} similar past threads`);

            // Your agent logic here — call OpenAI, Claude, etc.
            const reply = await generateReply(history, similar);

            // Send the reply, threaded correctly
            await commune.messages.send({
                to: from_address,
                subject: `Re: ${event.data.subject}`,
                text: reply,
                inboxId: inbox_id,
                threadId: thread_id,
            });

            await commune.threads.setStatus(thread_id, 'resolved');
            break;
        }

        case 'message.sent': {
            console.log(`Message sent: ${event.data.message_id}`);
            break;
        }

        case 'sms.received': {
            const { phone_number_id, from_number, body } = event.data;
            console.log(`SMS from ${from_number}: ${body}`);
            // Handle inbound SMS...
            break;
        }

        default:
            console.log(`Unhandled event type: ${event.type}`);
    }
}

async function generateReply(threadHistory: string, similarCases: any[]): Promise<string> {
    // Replace with your preferred LLM call
    return "Thank you for reaching out. We've reviewed your request and will get back to you shortly.";
}

app.listen(3000, () => console.log('Webhook server running on :3000'));
```

### Why `express.raw()` matters

Commune signs the raw request body with HMAC-SHA256. If you parse the body with `express.json()` first, the body buffer is consumed and `verifyCommuneWebhook` cannot verify the signature. Always use `express.raw()` on webhook routes, then parse the JSON inside the handler after verification.

---

## Multi-agent coordination

Two TypeScript agents hand off work over email — useful for pipelines where different agents specialise in different parts of a workflow:

```typescript
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

// Agent A: Research agent — writes a summary and assigns to Agent B
async function researchAgent(topic: string): Promise<void> {
    const researchInbox = process.env.RESEARCH_INBOX_ID!;
    const writerInbox = process.env.WRITER_INBOX_ADDRESS!; // e.g. writer@yourteam.commune.email

    // Do research work...
    const summary = await conductResearch(topic);

    // Hand off to the writer agent via email
    const msg = await commune.messages.send({
        to: writerInbox,
        subject: `Research complete: ${topic}`,
        text: JSON.stringify({ topic, summary, instructions: 'Write a 3-paragraph summary.' }),
        inboxId: researchInbox,
    });

    console.log(`Handed off to writer agent. Thread: ${msg.threadId}`);
}

// Agent B: Writer agent — receives the handoff, writes content, replies
async function writerAgent(webhookEvent: any): Promise<void> {
    const { thread_id, from_address, text, inbox_id } = webhookEvent.data;

    const payload = JSON.parse(text) as { topic: string; summary: string; instructions: string };

    // Do writing work...
    const content = await writeContent(payload.summary, payload.instructions);

    // Reply into the same thread — creates an auditable chain
    await commune.messages.send({
        to: from_address,
        subject: `Re: Research complete: ${payload.topic}`,
        text: content,
        inboxId: inbox_id,
        threadId: thread_id,
    });
}

async function conductResearch(topic: string): Promise<string> {
    return `Research findings for: ${topic}`;
}

async function writeContent(summary: string, instructions: string): Promise<string> {
    return `Written content based on: ${summary}`;
}
```

---

## SMS flow

```typescript
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function setupSMS(): Promise<void> {
    // Provision a real phone number
    const phone = await commune.phoneNumbers.provision();
    console.log(`Phone number provisioned: ${phone.number}`);

    // Send an SMS
    await commune.sms.send({
        to: '+14155551234',
        body: 'Your order #1234 has shipped and will arrive tomorrow.',
        phoneNumberId: phone.id,
    });

    console.log('SMS sent');
}

// Handle inbound SMS via webhook (same handler as email, different event type)
// event.type === 'sms.received'
// event.data.from_number, event.data.body, event.data.phone_number_id

setupSMS().catch(console.error);
```

---

## Tips

- Always use `express.raw()` on webhook routes — never `express.json()`. Parse inside the handler after verification.
- Acknowledge with `res.sendStatus(200)` before processing — Commune waits up to 10 seconds for a response
- Use `setImmediate()` or a queue for async processing — never `await` your handler logic before responding
- Type the `CommuneWebhookEvent` union — TypeScript will narrow the type in each `case` branch
- Pass `idempotency_key` on any `messages.send()` call that might be retried — prevents duplicate sends

---

[Back to main README](../README.md)
