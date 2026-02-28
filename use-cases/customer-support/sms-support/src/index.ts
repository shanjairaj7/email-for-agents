/**
 * SMS Customer Support Agent — TypeScript
 *
 * Express webhook handler for inbound SMS messages from Commune.
 * On each inbound message:
 *   1. Parse the URL-encoded Twilio-style payload Commune sends
 *   2. Load the full conversation history for this number
 *   3. Generate a reply with OpenAI (under 160 chars)
 *   4. Send the reply via commune.sms.send()
 *
 * Commune routes inbound SMS to your webhook as URL-encoded form data
 * using Twilio's callback format: { From, To, Body, MessageSid, ... }
 *
 * Install:  npm install
 * Run:      npm run dev
 *
 * Register your webhook once (run separately or in a setup script):
 *   const numbers = await commune.phoneNumbers.list();
 *   await commune.phoneNumbers.setWebhook(numbers[0].id, {
 *     endpoint: 'https://your-app.railway.app/sms/webhook',
 *     events: ['sms.received'],
 *   });
 */

import express from 'express';
import { CommuneClient } from 'commune-ai';
import OpenAI from 'openai';

const app  = express();
const port = process.env.PORT || 3000;

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai  = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

// ── Parse URL-encoded body ──────────────────────────────────────────────────
//
// Commune's SMS webhooks arrive as application/x-www-form-urlencoded,
// matching Twilio's callback format. Use express.urlencoded — NOT express.json.

app.use(express.urlencoded({ extended: false }));

// ── Resolve phone number on startup ────────────────────────────────────────

const numbers = await commune.phoneNumbers.list();
if (!numbers.length) {
  throw new Error(
    'No phone numbers found on this account. ' +
    'Provision one at commune.sh/dashboard and restart.'
  );
}

const PHONE_NUMBER_ID = numbers[0].id;
const PHONE_NUMBER    = numbers[0].number;

console.log(`SMS support agent using: ${PHONE_NUMBER}`);
console.log(`  POST /sms/webhook — receives inbound SMS`);
console.log(`  GET  /health      — health check\n`);

// ── Inbound SMS webhook ─────────────────────────────────────────────────────

app.post('/sms/webhook', async (req, res) => {
  // Acknowledge immediately — Commune (and Twilio) expect a fast 200.
  // All async work happens after the response is sent.
  res.status(200).send('<?xml version="1.0" encoding="UTF-8"?><Response></Response>');

  // Commune delivers Twilio-style URL-encoded fields:
  //   From       — the customer's phone number e.g. "+14155552671"
  //   To         — your Commune phone number
  //   Body       — the message text
  //   MessageSid — unique message ID
  const fromNumber: string = req.body.From;
  const messageBody: string = req.body.Body;
  const messageSid: string  = req.body.MessageSid;

  // Bail if the payload is missing required fields (e.g. a test ping)
  if (!fromNumber || !messageBody) {
    console.log('Webhook received without From/Body — ignoring.');
    return;
  }

  console.log(`\nInbound SMS [${messageSid}]`);
  console.log(`  From: ${fromNumber}`);
  console.log(`  Body: "${messageBody}"`);

  try {
    // Load the full conversation history between this customer and our number.
    // commune.sms.thread() returns messages in chronological order.
    const history = await commune.sms.thread(fromNumber, PHONE_NUMBER_ID);

    // Map to OpenAI chat turns:
    //   inbound  → role: "user"       (customer sent this)
    //   outbound → role: "assistant"  (we sent this)
    const chatHistory = history.map(m => ({
      role:    m.direction === 'inbound' ? 'user' as const : 'assistant' as const,
      content: m.body,
    }));

    // Generate a reply.
    // System prompt instructs the model to be concise — SMS has a 160-char limit
    // and carriers split longer messages into multiple segments.
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content:
            'You are a helpful SMS support agent for Acme SaaS. ' +
            'Keep every reply under 160 characters. ' +
            'Be direct and concise — no markdown, no bullet points, plain text only. ' +
            'If you cannot answer, say "Please email support@acme.io for help."',
        },
        ...chatHistory,
      ],
    });

    const reply = completion.choices[0].message.content!.trim();

    // Send the reply back to the customer on the same phone number
    await commune.sms.send({
      to:              fromNumber,
      body:            reply,
      phone_number_id: PHONE_NUMBER_ID,
    });

    console.log(`  Reply sent (${reply.length} chars): "${reply.slice(0, 100)}${reply.length > 100 ? '...' : ''}"`);

  } catch (err) {
    console.error('Error handling inbound SMS:', err);
    // Do not re-throw — we already sent 200. Log and move on.
  }
});

// ── Health check ────────────────────────────────────────────────────────────

app.get('/health', (_, res) => {
  res.json({ ok: true, phoneNumber: PHONE_NUMBER });
});

// ── Start server ────────────────────────────────────────────────────────────

app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
