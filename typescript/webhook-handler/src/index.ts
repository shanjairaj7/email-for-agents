/**
 * Commune Email Webhook Handler — TypeScript
 *
 * Receives inbound email events from Commune, verifies signatures,
 * and runs agent logic for each new email.
 *
 * Install:
 *   npm install
 *
 * Set up webhook in Commune:
 *   const inbox = await commune.inboxes.create({ localPart: 'support' });
 *   await commune.inboxes.setWebhook(inbox.domainId, inbox.id, {
 *     endpoint: 'https://your-app.railway.app/webhook',
 *     events: ['email.received'],
 *   });
 *
 * Usage:
 *   npm run dev
 */
import express from 'express';
import { CommuneClient, verifyCommuneWebhook, type InboundEmailWebhookPayload } from 'commune-ai';
import OpenAI from 'openai';

const app = express();
const port = process.env.PORT || 3000;

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

// Parse raw body for signature verification — must come BEFORE json parser
app.use('/webhook', express.raw({ type: 'application/json' }));
app.use(express.json());

// ── Webhook endpoint ───────────────────────────────────────────────────────

app.post('/webhook', async (req, res) => {
  // 1. Verify webhook signature (prevents spoofed requests)
  const rawBody = req.body.toString('utf8');
  try {
    verifyCommuneWebhook({
      rawBody,
      timestamp: req.headers['x-commune-timestamp'] as string,
      signature: req.headers['x-commune-signature'] as string,
      secret: process.env.COMMUNE_WEBHOOK_SECRET!,
    });
  } catch (err) {
    console.error('Invalid webhook signature:', err);
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // 2. Parse payload
  const payload: InboundEmailWebhookPayload = JSON.parse(rawBody);
  const { message, extractedData, security } = payload;

  // Only handle inbound emails
  if (message.direction !== 'inbound') {
    return res.status(200).json({ ok: true });
  }

  console.log(`\nInbound email`);
  console.log(`  Thread: ${message.thread_id}`);
  console.log(`  Subject: ${message.metadata.subject}`);

  // 3. Check security flags (Commune scans all inbound emails automatically)
  if (security?.spam.flagged) {
    console.log('  Spam detected — skipping');
    return res.status(200).json({ ok: true, skipped: 'spam' });
  }
  if (security?.prompt_injection.detected && security.prompt_injection.risk_level !== 'low') {
    console.log(`  Prompt injection detected (${security.prompt_injection.risk_level}) — skipping`);
    return res.status(200).json({ ok: true, skipped: 'prompt_injection' });
  }

  // 4. Acknowledge webhook immediately — process async so Commune doesn't time out
  res.status(200).json({ ok: true });

  // 5. Get sender email
  const sender = message.participants.find(p => p.role === 'sender')?.identity;
  if (!sender) return;

  // 6. Use extracted data if available (configured per-inbox JSON schema extraction)
  //    Commune can automatically parse structured fields out of each email body.
  const intent = extractedData?.intent;
  const urgency = extractedData?.urgency;
  if (intent) {
    console.log(`  Extracted intent: ${intent}, urgency: ${urgency}`);
  }

  try {
    // 7. Load thread history for context — lets the LLM see the full conversation
    const threadMessages = await commune.threads.messages(message.thread_id);
    const history = threadMessages.map(m => ({
      role: m.direction === 'inbound' ? 'user' as const : 'assistant' as const,
      content: m.content || '',
    }));

    // 8. Generate reply with OpenAI
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: `You are a helpful support agent. Reply professionally and concisely.
${intent ? `The email intent has been classified as: ${intent} (urgency: ${urgency})` : ''}
Sign off as "Support Team".`,
        },
        ...history,
      ],
    });

    const reply = completion.choices[0].message.content!;

    // 9. Send reply in the same thread — thread_id keeps it in the email chain
    await commune.messages.send({
      to: sender,
      subject: `Re: ${message.metadata.subject || ''}`,
      text: reply,
      inboxId: payload.inboxId,
      thread_id: message.thread_id,
    });

    console.log(`  Reply sent to ${sender}`);

    // 10. Update thread status so it's visible in Commune dashboard
    await commune.threads.setStatus(message.thread_id, 'waiting');
    if (urgency === 'high') {
      await commune.threads.addTags(message.thread_id, ['urgent']);
    }

  } catch (err) {
    console.error('Error handling email:', err);
  }
});

// ── Health check ───────────────────────────────────────────────────────────

app.get('/health', (_, res) => res.json({ ok: true }));

app.listen(port, () => {
  console.log(`Commune webhook handler running on port ${port}`);
  console.log(`  POST /webhook — receives inbound email events`);
  console.log(`  GET  /health  — health check`);
});
