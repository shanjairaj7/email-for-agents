/**
 * Two-Way SMS Handler — powered by Commune
 *
 * Receives inbound SMS via webhook, loads conversation history,
 * generates a reply with OpenAI, and sends it back.
 *
 * Commune fires URL-encoded POST bodies (Twilio-compatible) with fields:
 *   From       — sender's phone number
 *   To         — your Commune phone number
 *   Body       — message text
 *   MessageSid — unique message ID
 *
 * Usage:
 *   cp ../.env.example .env    # fill in keys
 *   npm install
 *   npm run dev
 */
import express from 'express';
import OpenAI from 'openai';
import { CommuneClient } from 'commune-ai';

const app = express();
const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai  = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

// Parse URL-encoded bodies — Commune SMS webhooks are Twilio-compatible format
app.use(express.urlencoded({ extended: false }));

const PHONE_NUMBER_ID = process.env.COMMUNE_PHONE_NUMBER_ID!;
const MAX_SMS_LENGTH  = 160;

// ─── Webhook handler ──────────────────────────────────────────────────────────

app.post('/sms-webhook', async (req, res) => {
  const from:       string = req.body.From;
  const to:         string = req.body.To;
  const body:       string = req.body.Body;
  const messageSid: string = req.body.MessageSid;

  if (!from || !body) {
    return res.sendStatus(400);
  }

  // Acknowledge immediately — return 200 before the async work starts
  res.sendStatus(200);

  console.log(`[${new Date().toISOString()}] SMS from ${from}: ${body}`);

  try {
    await handleInboundSms({ from, to, body, messageSid });
  } catch (err) {
    console.error('Error handling inbound SMS:', err);
  }
});

// ─── Core logic ───────────────────────────────────────────────────────────────

async function handleInboundSms({
  from,
  body,
}: {
  from:       string;
  to:         string;
  body:       string;
  messageSid: string;
}) {
  // 1. Load full conversation history with this number
  const history = await commune.sms.thread(from, PHONE_NUMBER_ID);
  // history is SmsMessage[] sorted oldest → newest
  // Each message: { direction: 'inbound' | 'outbound', content, created_at }

  // 2. Build the messages array for OpenAI
  //    Map Commune direction to OpenAI role:
  //    'inbound'  → 'user'      (message from the SMS user)
  //    'outbound' → 'assistant' (previous replies from our agent)
  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    {
      role:    'system',
      content: [
        'You are a helpful AI assistant responding to SMS messages.',
        'Keep replies concise — under 160 characters.',
        'Be friendly and direct. No markdown, no bullet points.',
        'If you cannot help with something, say so briefly.',
      ].join(' '),
    },
    ...history.map(msg => ({
      role:    (msg.direction === 'inbound' ? 'user' : 'assistant') as 'user' | 'assistant',
      content: msg.content,
    })),
    // The current inbound message is already in history, but include it
    // explicitly in case the history fetch raced with the webhook delivery
    {
      role:    'user' as const,
      content: body,
    },
  ];

  // 3. Generate reply
  const completion = await openai.chat.completions.create({
    model:      'gpt-4o-mini',
    messages,
    max_tokens: 100,   // keeps reply well under 160 chars
  });

  const reply = (completion.choices[0].message.content ?? '').trim().slice(0, MAX_SMS_LENGTH);

  if (!reply) {
    console.warn('OpenAI returned empty reply — skipping send');
    return;
  }

  // 4. Send reply back to the user
  await commune.sms.send({
    to:              from,
    body:            reply,
    phone_number_id: PHONE_NUMBER_ID,
  });

  console.log(`  Replied to ${from}: ${reply}`);
}

// ─── Startup ──────────────────────────────────────────────────────────────────

async function main() {
  if (!PHONE_NUMBER_ID) {
    throw new Error('COMMUNE_PHONE_NUMBER_ID is required. Set it in your .env file.');
  }

  const PORT = process.env.PORT || 3000;

  app.listen(PORT, () => {
    console.log(`Two-way SMS handler listening on port ${PORT}`);
    console.log(`POST /sms-webhook`);
    console.log(`Phone number ID: ${PHONE_NUMBER_ID}`);
  });
}

main().catch(console.error);
