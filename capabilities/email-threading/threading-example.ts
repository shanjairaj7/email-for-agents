/**
 * Email Threading Example (TypeScript)
 * Full send-detect-reply cycle:
 *   1. Create an inbox
 *   2. Send an opening email (starts a thread)
 *   3. List threads to find it
 *   4. Send a follow-up reply in the same thread
 *   5. Read all messages in the thread
 */

import { CommuneClient } from "commune-ai";

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const TO_ADDRESS = process.env.TEST_EMAIL!;

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  // -------------------------------------------------------------------------
  // 1. Create an inbox
  // -------------------------------------------------------------------------
  const inbox = await commune.inboxes.create({ localPart: "thread-demo-ts" });
  console.log(`Inbox: ${inbox.address}`);

  // -------------------------------------------------------------------------
  // 2. Send the opening message — starts a new thread
  // -------------------------------------------------------------------------
  const result = await commune.messages.send({
    to: TO_ADDRESS,
    subject: "Threading demo (TS) — message 1",
    text: [
      "Hi,",
      "",
      "This is the first message in a thread.",
      "",
      "The next message from the agent will appear in this same thread",
      "in your inbox — no new email chain.",
      "",
      "— Your agent",
    ].join("\n"),
    inboxId: inbox.id,
  });

  const threadId = result.thread_id;
  console.log(`Message 1 sent. Thread ID: ${threadId}`);

  // -------------------------------------------------------------------------
  // 3. List threads to inspect the thread object
  // -------------------------------------------------------------------------
  await sleep(1000);
  const { data: threads } = await commune.threads.list({
    inbox_id: inbox.id,
    limit: 5,
  });

  console.log(`\nThreads in inbox (${threads.length} found):`);
  for (const t of threads) {
    console.log(`  thread_id     : ${t.thread_id}`);
    console.log(`  subject       : ${t.subject}`);
    console.log(`  last_direction: ${t.last_direction}`);
    console.log(`  message_count : ${t.message_count}`);
  }

  // -------------------------------------------------------------------------
  // 4. Send a follow-up reply in the same thread
  // -------------------------------------------------------------------------
  console.log("\nSending follow-up reply in same thread...");
  await commune.messages.send({
    to: TO_ADDRESS,
    subject: "Re: Threading demo (TS) — message 1",
    text: [
      "Hi again,",
      "",
      "This is message 2 — same thread_id, so it appears inline",
      "in your inbox under the original email.",
      "",
      "Commune injected In-Reply-To and References headers automatically.",
      "",
      "— Your agent",
    ].join("\n"),
    inboxId: inbox.id,
    thread_id: threadId, // ← same thread
  });
  console.log("Message 2 sent (in-thread reply).");

  // -------------------------------------------------------------------------
  // 5. Send a third message
  // -------------------------------------------------------------------------
  await commune.messages.send({
    to: TO_ADDRESS,
    subject: "Re: Threading demo (TS) — message 1",
    text: [
      "Hi,",
      "",
      "This is message 3 — still the same thread.",
      "",
      "Marking thread as closed now.",
      "",
      "— Your agent",
    ].join("\n"),
    inboxId: inbox.id,
    thread_id: threadId,
  });
  console.log("Message 3 sent.");

  // Mark thread closed
  await commune.threads.setStatus(threadId, "closed");
  console.log("Thread marked closed.");

  // -------------------------------------------------------------------------
  // 6. Read all messages in the thread
  // -------------------------------------------------------------------------
  await sleep(1000);
  const messages = await commune.threads.messages(threadId);

  console.log(`\nAll messages in thread ${threadId}:`);
  messages.forEach((msg, i) => {
    const direction =
      msg.direction === "outbound" ? "outbound →" : "← inbound";
    const preview = msg.content.slice(0, 60).replace(/\n/g, " ") + "...";
    console.log(`  [${i + 1}] ${direction} | ${msg.created_at} | ${preview}`);
  });

  console.log("\nDone. Check your inbox — all three messages appear in one thread.");
}

main().catch(console.error);
