/**
 * SMS Lead Qualification Agent
 * ==============================
 * Express server with two endpoints:
 *
 *   POST /lead          — receive a new lead (from a form, CRM webhook, etc.)
 *                         immediately sends a qualifying SMS
 *
 *   POST /sms/webhook   — Commune delivers inbound SMS replies here
 *                         runs the multi-turn qualification conversation
 *
 * Qualification flow (up to 3 questions):
 *   1. Are you looking to implement within the next 3 months?
 *   2. What is your budget range?
 *   3. Are you the decision maker?
 *
 * Score >= 2 → email the sales team with a lead summary
 * Score < 2  → polite "we'll be in touch" SMS
 *
 * State is stored in memory (Map). For production, swap for SQLite or Redis.
 */

import express, { Request, Response } from 'express';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import { CommuneClient } from 'commune-ai';

dotenv.config();

// ---------------------------------------------------------------------------
// Clients
// ---------------------------------------------------------------------------

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

const PHONE_NUMBER_ID = process.env.COMMUNE_PHONE_NUMBER_ID!;
const INBOX_ID = process.env.COMMUNE_INBOX_ID!;
const SALES_EMAIL = process.env.SALES_EMAIL!;
const PORT = parseInt(process.env.PORT ?? '3000', 10);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Lead {
  name: string;
  phone: string;    // E.164 format, e.g. +15551234567
  email: string;
  source: string;
}

type QualStep = 'timeline' | 'budget' | 'decision_maker' | 'done';

interface ConversationState {
  lead: Lead;
  step: QualStep;
  score: number;
  answers: Record<string, string>;
  startedAt: Date;
}

// ---------------------------------------------------------------------------
// In-memory state (phone number → conversation)
// ---------------------------------------------------------------------------

// Key: remote phone number (E.164)
const conversations = new Map<string, ConversationState>();

// ---------------------------------------------------------------------------
// Qualification questions and scoring
// ---------------------------------------------------------------------------

const QUESTIONS: Record<QualStep, string> = {
  timeline:
    'are you looking to implement this within the next 3 months? Reply YES or NO.',
  budget:
    'what is your rough budget range? Reply A for under $5k, B for $5k–$20k, or C for over $20k.',
  decision_maker:
    'are you the primary decision maker for this purchase? Reply YES or NO.',
  done: '',
};

/**
 * Evaluate a raw SMS reply against the current qualification step.
 * Returns 1 if the answer is positive/qualifying, 0 otherwise.
 */
function scoreAnswer(step: QualStep, reply: string): number {
  const r = reply.trim().toUpperCase();
  if (step === 'timeline') return r.startsWith('Y') ? 1 : 0;
  if (step === 'budget') return r === 'B' || r === 'C' ? 1 : 0;
  if (step === 'decision_maker') return r.startsWith('Y') ? 1 : 0;
  return 0;
}

/**
 * Return the next step in the qualification sequence.
 */
function nextStep(current: QualStep): QualStep {
  const order: QualStep[] = ['timeline', 'budget', 'decision_maker', 'done'];
  const idx = order.indexOf(current);
  return order[idx + 1] ?? 'done';
}

// ---------------------------------------------------------------------------
// OpenAI: generate lead summary for sales team email
// ---------------------------------------------------------------------------

async function buildLeadSummary(state: ConversationState): Promise<string> {
  const { lead, answers, score } = state;
  const prompt = `Write a concise, structured lead summary for a sales rep.

Lead:
  Name: ${lead.name}
  Email: ${lead.email}
  Phone: ${lead.phone}
  Source: ${lead.source}

Qualification answers:
  Timeline (within 3 months?): ${answers.timeline ?? 'not answered'}
  Budget range: ${answers.budget ?? 'not answered'}
  Decision maker?: ${answers.decision_maker ?? 'not answered'}

Qualification score: ${score}/3

Keep it under 8 bullet points. Start with a one-sentence verdict.`;

  const response = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.3,
  });

  return response.choices[0].message.content?.trim() ?? 'Summary unavailable.';
}

// ---------------------------------------------------------------------------
// POST /lead — new lead intake
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json());

app.post('/lead', async (req: Request, res: Response): Promise<void> => {
  const { name, phone, email, source } = req.body as Lead;

  if (!name || !phone || !email) {
    res.status(400).json({ error: 'name, phone, and email are required' });
    return;
  }

  console.log(`[NEW LEAD] ${name} <${email}> from ${source ?? 'unknown'}`);

  // Initialise conversation state
  conversations.set(phone, {
    lead: { name, phone, email, source: source ?? 'unknown' },
    step: 'timeline',
    score: 0,
    answers: {},
    startedAt: new Date(),
  });

  // Send the first qualifying question immediately
  const firstName = name.split(' ')[0];
  const firstQuestion = QUESTIONS['timeline'];

  await commune.sms.send({
    to: phone,
    body: `Hi ${firstName}! Thanks for your interest. Quick question — ${firstQuestion}`,
    phone_number_id: PHONE_NUMBER_ID,
  });

  console.log(`[SMS SENT] Opening question to ${phone}`);
  res.status(200).json({ ok: true, message: 'Qualification started' });
});

// ---------------------------------------------------------------------------
// POST /sms/webhook — Commune delivers inbound SMS replies here
// ---------------------------------------------------------------------------

app.post('/sms/webhook', async (req: Request, res: Response): Promise<void> => {
  // Acknowledge immediately — Commune expects a fast 200
  res.status(200).json({ ok: true });

  const { from, body: replyText } = req.body as { from: string; body: string };

  if (!from || !replyText) return;

  const state = conversations.get(from);

  if (!state) {
    // Unknown number — someone texted the number directly
    console.log(`[UNKNOWN] SMS from ${from}: "${replyText}" — no active session`);
    await commune.sms.send({
      to: from,
      body: "Hi! We don't have an active session for this number. Visit our website to get started.",
      phone_number_id: PHONE_NUMBER_ID,
    });
    return;
  }

  if (state.step === 'done') return; // sequence already complete

  const { lead, step } = state;
  console.log(`[REPLY] ${from} (step: ${step}): "${replyText}"`);

  // Record the answer and update score
  state.answers[step] = replyText.trim();
  state.score += scoreAnswer(step, replyText);
  state.step = nextStep(step);

  // ---- More questions to ask --------------------------------------------
  if (state.step !== 'done') {
    const question = QUESTIONS[state.step];
    await commune.sms.send({
      to: from,
      body: question,
      phone_number_id: PHONE_NUMBER_ID,
    });
    console.log(`[SMS SENT] Follow-up question (${state.step}) to ${from}`);
    return;
  }

  // ---- All questions answered — evaluate --------------------------------
  console.log(`[QUALIFIED?] ${lead.name} scored ${state.score}/3`);

  if (state.score >= 2) {
    // Qualified — email the sales team
    const summary = await buildLeadSummary(state);

    await commune.messages.send({
      to: SALES_EMAIL,
      subject: `Qualified lead: ${lead.name} (${lead.source})`,
      text: `A new lead has been qualified via SMS.\n\n${summary}\n\n---\nGenerated by SMS Lead Qualification Agent`,
      inboxId: INBOX_ID,
    });

    console.log(`[QUALIFIED] Email sent to sales team for ${lead.name}`);

    await commune.sms.send({
      to: from,
      body: `Thanks ${lead.name.split(' ')[0]}! A member of our team will reach out to ${lead.email} within one business day.`,
      phone_number_id: PHONE_NUMBER_ID,
    });
  } else {
    // Not qualified — polite close
    console.log(`[NOT QUALIFIED] ${lead.name} — score ${state.score}/3`);

    await commune.sms.send({
      to: from,
      body: `Thanks for your time, ${lead.name.split(' ')[0]}! We'll keep your details on file and reach out if a good fit comes up.`,
      phone_number_id: PHONE_NUMBER_ID,
    });
  }
});

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

app.listen(PORT, () => {
  console.log(`\nSMS Lead Qualification Agent running on port ${PORT}`);
  console.log(`  POST /lead        — submit a new lead`);
  console.log(`  POST /sms/webhook — Commune SMS webhook\n`);
});
