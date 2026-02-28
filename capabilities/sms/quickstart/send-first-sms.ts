/**
 * Send your first SMS — powered by Commune
 *
 * Usage:
 *   export COMMUNE_API_KEY=comm_...
 *   npx tsx send-first-sms.ts
 */
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function main() {
  const numbers = await commune.phoneNumbers.list();
  if (numbers.length === 0) {
    throw new Error('No phone numbers found. Provision one at https://commune.email/dashboard');
  }

  const result = await commune.sms.send({
    to:              '+14155551234',          // replace with your number
    body:            'Hello from my AI agent!',
    phone_number_id: numbers[0].id,
  });

  console.log(`Sent! Message ID: ${result.message_id}`);
  console.log(`      Thread ID:  ${result.thread_id}`);
  console.log(`      Status:     ${result.status}`);
}

main().catch(console.error);
