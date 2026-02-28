/**
 * Acknowledgment webhook handler
 * Commune calls POST /email-webhook whenever a new email arrives in the alerts inbox.
 * If the body contains "ACK" or "acknowledged", we mark the alert resolved.
 */

import express, { Request, Response } from "express";
import fs from "fs";
import path from "path";
import { verifyCommuneWebhook } from "commune-ai";

const app = express();
app.use(express.json());

const STATE_FILE = path.resolve(__dirname, "../alert_state.json");
const WEBHOOK_SECRET = process.env.COMMUNE_WEBHOOK_SECRET ?? "";

// ---------------------------------------------------------------------------
// State helpers
// ---------------------------------------------------------------------------

interface AlertState {
  [alertId: string]: {
    alert_id: string;
    title: string;
    severity: string;
    thread_id: string;
    acknowledged: boolean;
    escalated: boolean;
    created_at: string;
    acknowledged_at?: string;
  };
}

function loadState(): AlertState {
  if (!fs.existsSync(STATE_FILE)) return {};
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
}

function saveState(state: AlertState): void {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function findAlertByThreadId(threadId: string, state: AlertState): string | null {
  for (const [alertId, alert] of Object.entries(state)) {
    if (alert.thread_id === threadId) return alertId;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Webhook route
// ---------------------------------------------------------------------------

app.post("/email-webhook", (req: Request, res: Response) => {
  // Verify the webhook signature
  if (WEBHOOK_SECRET) {
    const signature = req.headers["commune-signature"] as string | undefined;
    const rawBody = JSON.stringify(req.body);
    if (!signature || !verifyCommuneWebhook(rawBody, signature, WEBHOOK_SECRET)) {
      return res.status(401).json({ error: "Invalid webhook signature" });
    }
  }

  const { message, thread } = req.body as {
    message: {
      direction: "inbound" | "outbound";
      content: string;
      thread_id: string;
    };
    thread: {
      thread_id: string;
      subject: string;
    };
  };

  // Only care about inbound messages (engineer replies)
  if (message.direction !== "inbound") {
    return res.json({ status: "ignored", reason: "outbound message" });
  }

  const body = (message.content ?? "").toLowerCase();
  const isAcknowledgment =
    body.includes("ack") ||
    body.includes("acknowledged") ||
    body.includes("resolved") ||
    body.includes("on it") ||
    body.includes("looking into it");

  if (!isAcknowledgment) {
    return res.json({ status: "ignored", reason: "not an acknowledgment" });
  }

  // Find the alert by thread_id
  const state = loadState();
  const alertId = findAlertByThreadId(message.thread_id, state);

  if (!alertId) {
    console.log(`[webhook] No alert found for thread_id=${message.thread_id}`);
    return res.json({ status: "ignored", reason: "no matching alert" });
  }

  if (state[alertId].acknowledged) {
    return res.json({ status: "already_acknowledged" });
  }

  // Mark acknowledged
  state[alertId].acknowledged = true;
  state[alertId].acknowledged_at = new Date().toISOString();
  saveState(state);

  console.log(
    `[webhook] Alert ${alertId} acknowledged via email reply — stopping escalation.`
  );

  return res.json({ status: "acknowledged", alert_id: alertId });
});

app.get("/health", (_req, res) => res.json({ ok: true }));

const PORT = parseInt(process.env.PORT ?? "3001", 10);
app.listen(PORT, () => {
  console.log(`Acknowledgment webhook handler running on port ${PORT}`);
});

export default app;
