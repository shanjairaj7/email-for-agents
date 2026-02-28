/**
 * Orchestrator Agent
 *
 * Receives inbound user emails, classifies intent, and either:
 *   - Replies directly for simple queries
 *   - Forwards to the appropriate specialist for complex ones
 *
 * The key coordination primitive: when forwarding, the orchestrator
 * includes the user's original thread_id in the forwarded email body.
 * The specialist uses it to reply directly in the user's thread —
 * no shared database required.
 */
import { Router, type Request, type Response } from 'express';
import { CommuneClient, verifyCommuneWebhook, type InboundEmailWebhookPayload } from 'commune-ai';
import OpenAI from 'openai';
import type { ClassificationResult, ForwardedTaskPayload } from '../types.js';

export function createOrchestratorRouter(
  commune: CommuneClient,
  openai: OpenAI,
): Router {
  const router = Router();

  // Raw body required for signature verification
  router.use(express_raw_middleware());

  router.post('/', async (req: Request, res: Response) => {
    // 1. Verify webhook signature
    const rawBody = req.body.toString('utf8');
    try {
      verifyCommuneWebhook({
        rawBody,
        timestamp: req.headers['x-commune-timestamp'] as string,
        signature: req.headers['x-commune-signature'] as string,
        secret: process.env.COMMUNE_WEBHOOK_SECRET!,
      });
    } catch {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    const payload: InboundEmailWebhookPayload = JSON.parse(rawBody);
    const { message } = payload;

    // Only handle inbound emails
    if (message.direction !== 'inbound') {
      return res.status(200).json({ ok: true });
    }

    const sender = message.participants.find(p => p.role === 'sender')?.identity;
    if (!sender) return res.status(200).json({ ok: true });

    console.log(`\n[Orchestrator] Email from ${sender}`);
    console.log(`  Subject: ${message.metadata.subject}`);

    // 2. Acknowledge immediately
    res.status(200).json({ ok: true });

    try {
      // 3. Classify intent with LLM
      const classification = await classifyEmail(openai, {
        subject: message.metadata.subject || '',
        content: message.content || '',
      });

      console.log(`  Intent: ${classification.intent} — ${classification.summary}`);

      if (classification.intent === 'simple' && classification.directReply) {
        // 4a. Simple query: reply directly, no forwarding needed
        await commune.messages.send({
          to: sender,
          subject: `Re: ${message.metadata.subject || ''}`,
          text: classification.directReply,
          inboxId: payload.inboxId,
          thread_id: message.thread_id,
        });
        await commune.threads.setStatus(message.thread_id, 'closed');
        console.log(`  Direct reply sent, thread closed`);

      } else {
        // 4b. Complex query: forward to specialist via email
        //     The specialist inbox address comes from environment config.
        const specialistInbox =
          classification.intent === 'billing'
            ? process.env.SPECIALIST_BILLING_INBOX!
            : process.env.SPECIALIST_TECHNICAL_INBOX!;

        // Embed the original thread_id in the forwarded payload.
        // This is the coordination primitive — no shared DB needed.
        const forwardedPayload: ForwardedTaskPayload = {
          userEmail: sender,
          originalSubject: message.metadata.subject || '',
          originalThreadId: message.thread_id,
          userInboxId: payload.inboxId,
          userContent: message.content || '',
          summary: classification.summary,
        };

        await commune.messages.send({
          to: specialistInbox,
          subject: `[Task] ${classification.intent.toUpperCase()} — ${message.metadata.subject || ''}`,
          text: [
            `Forwarded from orchestrator. Please reply to the user in their original thread.`,
            ``,
            `TASK_PAYLOAD:${JSON.stringify(forwardedPayload)}`,
          ].join('\n'),
          inboxId: payload.inboxId,
        });

        // Mark the user's thread as waiting for specialist
        await commune.threads.setStatus(message.thread_id, 'waiting');
        await commune.threads.addTags(message.thread_id, [classification.intent]);
        console.log(`  Forwarded to ${classification.intent} specialist`);
      }

    } catch (err) {
      console.error('[Orchestrator] Error:', err);
    }
  });

  return router;
}

// ── Classification ─────────────────────────────────────────────────────────

async function classifyEmail(
  openai: OpenAI,
  email: { subject: string; content: string },
): Promise<ClassificationResult> {
  const completion = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    response_format: { type: 'json_object' },
    messages: [
      {
        role: 'system',
        content: `You are an email triage agent. Classify inbound emails and respond in JSON.

Intents:
- "simple": FAQs, greetings, general questions you can answer yourself
- "billing": payment issues, invoices, refunds, subscriptions
- "technical": bugs, errors, API questions, integration help

Return:
{
  "intent": "simple" | "billing" | "technical",
  "summary": "one sentence describing what the user wants",
  "directReply": "full reply text if intent is simple, omit otherwise"
}`,
      },
      {
        role: 'user',
        content: `Subject: ${email.subject}\n\n${email.content}`,
      },
    ],
  });

  return JSON.parse(completion.choices[0].message.content!) as ClassificationResult;
}

// ── Middleware helper ──────────────────────────────────────────────────────

/**
 * Returns express.raw() middleware. Extracted to avoid importing express
 * at module level — the router factory is called after express is initialised.
 */
function express_raw_middleware() {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const express = require('express');
  return express.raw({ type: 'application/json' });
}
