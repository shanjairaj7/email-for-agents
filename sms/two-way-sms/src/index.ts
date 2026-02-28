/**
 * Two-Way SMS Agent — TypeScript
 *
 * Receives inbound SMS messages via Commune webhook, generates a reply
 * with OpenAI, and sends it back. The SMS equivalent of the email
 * webhook handler.
 *
 * Install:
 *   npm install
 *
 * Set up webhook in Commune:
 *   const numbers = await commune.phoneNumbers.list();
 *   await commune.phoneNumbers.setWebhook(numbers[0].id, {
 *     endpoint: 'https://your-app.railway.app/sms/webhook',
 *     events: ['sms.received'],
 *   });
 *
 * Usage:
 *   npm run dev
 */
import express from 'express';
import { CommuneClient } from 'commune-ai';
import OpenAI from 'openai';

const app = express();
const port = process.env.PORT || 3000;

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

// ── Get phone number ───────────────────────────────────────────────────────

const numbers = await commune.phoneNumbers.list();
if (!numbers.length) {
  throw new Error('No phone numbers found. Provision one at commune.email/dashboard.');
}
const PHONE_NUMBER_ID = numbers[0].id;
const PHONE_NUMBER = numbers[0].number;

console.log(`SMS agent using phone number: ${PHONE_NUMBER}`);

// ── Middleware ─────────────────────────────────────────────────────────────

app.use(express.json());

// ── Inbound SMS webhook ────────────────────────────────────────────────────

app.post('/sms/webhook', async (req, res) => {
  const { event, message } = req.body as InboundSmsWebhookPayload;

  // Only handle inbound SMS messages
  if (event !== 'sms.received' || message?.direction !== 'inbound') {
    return res.status(200).json({ ok: true });
  }

  const from = message.from;
  const body = message.body;

  console.log(`\nInbound SMS from ${from}: "${body}"`);

  // Acknowledge immediately
  res.status(200).json({ ok: true });

  try {
    // Load conversation history so the LLM has context
    const history = await commune.sms.thread(from, PHONE_NUMBER_ID);
    const messages = history.map(m => ({
      role: m.direction === 'inbound' ? 'user' as const : 'assistant' as const,
      content: m.body,
    }));

    // Generate reply
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: `You are a helpful assistant replying via SMS. Keep replies concise — under 160 characters where possible. No markdown, no bullet points. Plain text only.`,
        },
        ...messages,
      ],
    });

    const reply = completion.choices[0].message.content!;

    // Send reply
    await commune.sms.send({
      to: from,
      body: reply,
      phone_number_id: PHONE_NUMBER_ID,
    });

    console.log(`  Reply sent: "${reply.slice(0, 80)}${reply.length > 80 ? '...' : ''}"`);

  } catch (err) {
    console.error('Error handling SMS:', err);
  }
});

// ── Health check ───────────────────────────────────────────────────────────

app.get('/health', (_, res) => res.json({ ok: true }));

app.listen(port, () => {
  console.log(`Two-way SMS agent running on port ${port}`);
  console.log(`  POST /sms/webhook — receives inbound SMS events`);
  console.log(`  GET  /health       — health check`);
});

// ── Types ──────────────────────────────────────────────────────────────────

interface InboundSmsWebhookPayload {
  event: string;
  message?: {
    message_id: string;
    direction: 'inbound' | 'outbound';
    from: string;
    to: string;
    body: string;
    phone_number_id: string;
    created_at: string;
  };
}
