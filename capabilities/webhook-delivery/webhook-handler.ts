/**
 * Production webhook handler — Commune email events
 *
 * Receives inbound email webhooks from Commune, verifies the HMAC-SHA256
 * signature, and processes the event asynchronously so Commune gets a
 * fast 200 OK and never triggers a retry.
 *
 * Usage:
 *   cp .env.example .env   # fill in your keys
 *   npm install
 *   npm run dev
 */
import express from 'express';
import { CommuneClient, verifyCommuneWebhook } from 'commune-ai';

const app = express();
const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

// IMPORTANT: use express.raw() — not express.json().
// verifyCommuneWebhook computes HMAC over the raw bytes. Parsing to JSON
// first changes the byte representation and the signature check will fail.
app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  // Verify the signature before touching the payload.
  // Throws if the signature is invalid or the timestamp is stale (> 5 min).
  let payload: ReturnType<typeof verifyCommuneWebhook>;
  try {
    payload = verifyCommuneWebhook({
      rawBody:   req.body,                                          // raw Buffer
      timestamp: req.headers['x-commune-timestamp'] as string,
      signature: req.headers['x-commune-signature'] as string,
      secret:    process.env.COMMUNE_WEBHOOK_SECRET!,
    });
  } catch (err) {
    console.error('Webhook signature verification failed:', err);
    return res.sendStatus(401);
  }

  // Acknowledge immediately — Commune retries if it doesn't get 200 within 10s.
  // All real work happens asynchronously after this line.
  res.sendStatus(200);

  // Process in the background
  handleEvent(payload).catch(err => {
    console.error('Error processing webhook event:', err);
  });
});

// ─── Event handler ────────────────────────────────────────────────────────────

async function handleEvent(payload: any) {
  const { event, data } = payload;

  if (event === 'email.received') {
    await handleEmailReceived(data);
  } else {
    console.log(`Unhandled event type: ${event}`);
  }
}

async function handleEmailReceived(data: {
  inbox_id:        string;
  inbox_address:   string;
  thread_id:       string;
  is_first_message: boolean;
  message_id:      string;
  from:            string;
  to:              string[];
  subject:         string;
  text:            string;
  html:            string;
  received_at:     string;
  extracted?:      Record<string, unknown>;   // present if inbox has an extraction schema
  attachments?:    Array<{
    filename:       string;
    content_type:   string;
    size_bytes:     number;
    attachment_id:  string;
  }>;
}) {
  console.log(`[${data.received_at}] New email in ${data.inbox_address}`);
  console.log(`  From:    ${data.from}`);
  console.log(`  Subject: ${data.subject}`);
  console.log(`  Thread:  ${data.thread_id} (${data.is_first_message ? 'new thread' : 'reply'})`);

  if (data.extracted) {
    console.log(`  Extracted:`, data.extracted);
  }

  if (data.attachments && data.attachments.length > 0) {
    console.log(`  Attachments: ${data.attachments.map(a => a.filename).join(', ')}`);
  }

  // ── Your agent logic goes here ──────────────────────────────────────────────
  //
  // Examples:
  //
  // 1. Search for similar past threads before drafting a reply:
  //    const similar = await commune.search.threads({
  //      query: data.text,
  //      inboxId: data.inbox_id,
  //      limit: 3,
  //    });
  //
  // 2. Send a reply in the same thread:
  //    await commune.messages.send({
  //      to:       data.from,
  //      subject: `Re: ${data.subject}`,
  //      text:    agentReply,
  //      inboxId: data.inbox_id,
  //      threadId: data.thread_id,   // keeps it in the same email thread
  //    });
  //
  // 3. Use structured extraction output to route the ticket:
  //    if (data.extracted?.urgency === 'high') {
  //      await notifyOnCall(data);
  //    }
  // ────────────────────────────────────────────────────────────────────────────
}

// ─── Start server ─────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Webhook handler listening on port ${PORT}`);
  console.log(`POST /webhook`);
});
