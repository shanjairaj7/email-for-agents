/**
 * Semantic search example — powered by Commune
 *
 * Shows how to search email threads with natural language queries.
 * Results are ranked by vector similarity (score 0.0 → 1.0), not keyword matching.
 *
 * Usage:
 *   export COMMUNE_API_KEY=comm_...
 *   npx tsx search-example.ts
 */
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function main() {
  // Find inbox (create one if needed)
  const inboxes = await commune.inboxes.list();
  let inboxId: string;

  if (inboxes.length === 0) {
    const inbox = await commune.inboxes.create({ localPart: 'support' });
    inboxId = inbox.id;
    console.log(`Created inbox: ${inbox.address}`);
  } else {
    inboxId = inboxes[0].id;
    console.log(`Using inbox: ${inboxes[0].address}`);
  }

  console.log();

  // Run a few different semantic searches.
  // These queries use natural language — they don't need to match the exact words
  // in the emails. "customer wants a refund" will surface threads about charge
  // disputes, billing errors, money-back requests, and so on.
  const queries = [
    'customer wants a refund',
    'login or authentication problems',
    'pricing and billing questions',
    'feature request or product feedback',
  ];

  for (const query of queries) {
    console.log(`Query: '${query}'`);

    const results = await commune.search.threads({ query, inboxId, limit: 3 });

    if (results.length === 0) {
      console.log('  No results found (inbox may be empty — send a few emails first)');
    } else {
      for (const r of results) {
        const subject = r.subject || '(no subject)';
        const participants = r.participants?.join(', ') ?? '';
        console.log(`  [${r.score.toFixed(2)}] ${subject} — thread: ${r.thread_id}`);
        if (participants) {
          console.log(`         participants: ${participants}`);
        }
      }
    }

    console.log();
  }
}

main().catch(console.error);
