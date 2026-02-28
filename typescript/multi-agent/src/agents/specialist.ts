/**
 * Specialist Agent
 *
 * Receives forwarded tasks from the orchestrator, generates an expert reply,
 * and sends it directly to the USER in their original thread.
 *
 * The key insight: the orchestrator embedded the user's original thread_id
 * in the forwarded email body. The specialist extracts it and uses it as
 * the thread_id when sending — so the user sees a seamless reply in their
 * original conversation, with no knowledge of the multi-agent system.
 */
import { Router, type Request, type Response } from 'express';
import { CommuneClient, verifyCommuneWebhook, type InboundEmailWebhookPayload } from 'commune-ai';
import OpenAI from 'openai';
import type { ForwardedTaskPayload } from '../types.js';

export type SpecialistDomain = 'billing' | 'technical';

const SYSTEM_PROMPTS: Record<SpecialistDomain, string> = {
  billing: `You are a billing support specialist. You help with payment issues, invoices,
refunds, and subscription questions. Be empathetic, clear, and precise about
financial details. Sign off as "Billing Team".`,

  technical: `You are a senior technical support engineer. You help with bugs, API integration,
configuration, and troubleshooting. Be thorough, provide concrete steps, and include
code examples where relevant. Sign off as "Technical Support Team".`,
};

export function createSpecialistRouter(
  domain: SpecialistDomain,
  commune: CommuneClient,
  openai: OpenAI,
): Router {
  const router = Router();

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

    if (message.direction !== 'inbound') {
      return res.status(200).json({ ok: true });
    }

    // 2. Acknowledge immediately
    res.status(200).json({ ok: true });

    // 3. Extract the forwarded task payload from the email body
    //    The orchestrator embedded it as: TASK_PAYLOAD:{...json...}
    const taskPayload = extractTaskPayload(message.content || '');
    if (!taskPayload) {
      console.log(`[${domain} specialist] No task payload found — ignoring`);
      return;
    }

    console.log(`\n[${domain} specialist] Task received`);
    console.log(`  User: ${taskPayload.userEmail}`);
    console.log(`  Summary: ${taskPayload.summary}`);
    console.log(`  Original thread: ${taskPayload.originalThreadId}`);

    try {
      // 4. Load the full user thread for context
      //    This gives the specialist the complete conversation history,
      //    not just the orchestrator's summary.
      const threadMessages = await commune.threads.messages(taskPayload.originalThreadId);
      const history = threadMessages.map(m => ({
        role: m.direction === 'inbound' ? 'user' as const : 'assistant' as const,
        content: m.content || '',
      }));

      // 5. Generate expert reply
      const completion = await openai.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: `${SYSTEM_PROMPTS[domain]}

Context from orchestrator: ${taskPayload.summary}`,
          },
          // Full conversation history gives specialist full context
          ...history,
        ],
      });

      const reply = completion.choices[0].message.content!;

      // 6. Send reply directly to the USER in their ORIGINAL thread.
      //    Using originalThreadId means the user sees this as a reply
      //    in their existing conversation — the multi-agent routing is invisible.
      await commune.messages.send({
        to: taskPayload.userEmail,
        subject: `Re: ${taskPayload.originalSubject}`,
        text: reply,
        inboxId: taskPayload.userInboxId,
        thread_id: taskPayload.originalThreadId,  // back in the user's thread
      });

      // 7. Mark the user's thread as resolved
      await commune.threads.setStatus(taskPayload.originalThreadId, 'closed');

      console.log(`  Reply sent to ${taskPayload.userEmail}, thread closed`);

    } catch (err) {
      console.error(`[${domain} specialist] Error:`, err);
    }
  });

  return router;
}

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Extracts the ForwardedTaskPayload JSON from the email body.
 * The orchestrator embeds it as a line starting with "TASK_PAYLOAD:".
 */
function extractTaskPayload(body: string): ForwardedTaskPayload | null {
  const line = body.split('\n').find(l => l.startsWith('TASK_PAYLOAD:'));
  if (!line) return null;
  try {
    return JSON.parse(line.slice('TASK_PAYLOAD:'.length)) as ForwardedTaskPayload;
  } catch {
    return null;
  }
}

function express_raw_middleware() {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const express = require('express');
  return express.raw({ type: 'application/json' });
}
