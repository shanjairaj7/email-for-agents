/**
 * One-time setup: create inbox and configure webhook endpoint.
 *
 * Run this once to wire up your Commune inbox to your webhook handler:
 *
 *   export COMMUNE_API_KEY=comm_...
 *   export WEBHOOK_URL=https://your-app.railway.app/webhook
 *   npx tsx webhook-setup.ts
 *
 * After running:
 *   1. Copy the webhook secret printed below into your .env as COMMUNE_WEBHOOK_SECRET
 *   2. Deploy webhook-handler.ts and start receiving emails in real time
 */
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function setup() {
  if (!process.env.WEBHOOK_URL) {
    throw new Error('Set WEBHOOK_URL — e.g. https://your-app.railway.app/webhook');
  }
  const webhookUrl = process.env.WEBHOOK_URL;

  // Create or find inbox
  const inboxes = await commune.inboxes.list();
  let inbox = inboxes.find(i => i.localPart === 'support');

  if (!inbox) {
    inbox = await commune.inboxes.create({ localPart: 'support' });
    console.log(`Created inbox: ${inbox.address}`);
  } else {
    console.log(`Found inbox: ${inbox.address}`);
  }

  if (!inbox.id || !inbox.address) {
    throw new Error('Inbox is missing id or address — something went wrong during creation');
  }

  // Get domain — needed for setWebhook
  const domains = await commune.domains.list();
  if (domains.length === 0) {
    throw new Error('No domains found. Add a domain in the Commune dashboard first.');
  }
  const domain = domains[0];

  // Configure webhook
  await commune.inboxes.setWebhook(domain.id, inbox.id, {
    endpoint: webhookUrl,
    events: ['email.received'],
  });

  console.log(`Webhook configured: ${webhookUrl}`);
  console.log();
  console.log('Next steps:');
  console.log('  1. Copy your webhook secret from the Commune dashboard');
  console.log('     Settings → Webhooks → your endpoint → Show secret');
  console.log('  2. Add it to your .env:');
  console.log('       COMMUNE_WEBHOOK_SECRET=whsec_...');
  console.log('  3. Deploy webhook-handler.ts');
  console.log(`  4. Send a test email to ${inbox.address} and watch it arrive`);
}

setup().catch(console.error);
