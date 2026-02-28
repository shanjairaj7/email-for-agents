/**
 * Multi-Agent Email Coordination — TypeScript
 *
 * Three agents coordinate by passing messages through real email threads.
 * No message bus, no shared database — just email and thread IDs.
 *
 * Architecture:
 *   1. User sends email → Orchestrator inbox
 *   2. Orchestrator classifies intent
 *      - Simple: replies directly
 *      - Billing/Technical: forwards to specialist, embeds original thread_id
 *   3. Specialist reads forwarded task, replies to USER in original thread
 *
 * Install:
 *   npm install
 *
 * Set up inboxes and webhooks in Commune:
 *   See README.md for the one-time setup script.
 *
 * Usage:
 *   npm run dev
 */
import express from 'express';
import { CommuneClient } from 'commune-ai';
import OpenAI from 'openai';
import { createOrchestratorRouter } from './agents/orchestrator.js';
import { createSpecialistRouter } from './agents/specialist.js';

const app = express();
const port = process.env.PORT || 3000;

// Shared clients — both agents use the same API key
const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });

// ── Mount agent routes ─────────────────────────────────────────────────────
//
// Each path corresponds to a different Commune inbox webhook.
// Register /webhook/orchestrator for your main inbox,
// /webhook/billing and /webhook/technical for the specialist inboxes.

app.use('/webhook/orchestrator', createOrchestratorRouter(commune, openai));
app.use('/webhook/billing', createSpecialistRouter('billing', commune, openai));
app.use('/webhook/technical', createSpecialistRouter('technical', commune, openai));

// ── Health check ───────────────────────────────────────────────────────────

app.get('/health', (_, res) => res.json({ ok: true }));

// ── Start ──────────────────────────────────────────────────────────────────

app.listen(port, () => {
  console.log(`Multi-agent server running on port ${port}`);
  console.log(`  POST /webhook/orchestrator — receives user emails`);
  console.log(`  POST /webhook/billing      — billing specialist`);
  console.log(`  POST /webhook/technical    — technical specialist`);
  console.log(`  GET  /health               — health check`);
  console.log(``);
  console.log(`Configure webhooks in Commune to point each inbox at the matching path.`);
  console.log(`See README.md for the setup script.`);
});
