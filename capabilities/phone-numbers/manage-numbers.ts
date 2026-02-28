/**
 * Phone number management — powered by Commune
 *
 * Full TypeScript API: search available numbers, provision, list, configure
 * webhooks, set auto-reply, and read SMS conversations.
 *
 * Usage:
 *   export COMMUNE_API_KEY=comm_...
 *   npx tsx manage-numbers.ts
 */
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });

async function main() {

  // ── Search available numbers ───────────────────────────────────────────────
  console.log('Available local numbers in area code 415:');
  const available = await commune.phoneNumbers.available({
    type: 'Local',
    area_code: '415',
  });

  for (const n of available.slice(0, 3)) {
    const sms   = n.capabilities.sms   ? 'SMS'   : '';
    const voice = n.capabilities.voice ? 'Voice' : '';
    const caps  = [sms, voice].filter(Boolean).join(', ');
    console.log(`  ${n.phoneNumber}  [${caps}]`);
  }
  console.log();

  // ── Provision a number ─────────────────────────────────────────────────────
  // Uncomment to actually provision:
  //
  // const provisioned = await commune.phoneNumbers.provision(available[0].phoneNumber);
  // console.log(`Provisioned: ${provisioned.number}  id=${provisioned.id}`);

  // ── List provisioned numbers ───────────────────────────────────────────────
  console.log('Numbers on your account:');
  const numbers = await commune.phoneNumbers.list();

  if (numbers.length === 0) {
    console.log('  No numbers yet. Provision one above or via the dashboard.');
    return;
  }

  for (const n of numbers) {
    const sms   = n.capabilities?.sms   ? 'SMS'   : '';
    const voice = n.capabilities?.voice ? 'Voice' : '';
    const caps  = [sms, voice].filter(Boolean).join(', ');
    console.log(`  ${n.number}  [${caps}]  id=${n.id}`);
  }
  console.log();

  const phone = numbers[0];

  // ── Configure webhook ──────────────────────────────────────────────────────
  // Point inbound SMS events at your handler.
  // The handler receives URL-encoded bodies — see capabilities/sms/two-way/
  //
  // await commune.phoneNumbers.setWebhook(phone.id, {
  //   endpoint: 'https://your-app.railway.app/sms-webhook',
  //   events: ['sms.received'],
  // });
  // console.log('Webhook configured');

  // ── Set friendly name and auto-reply ──────────────────────────────────────
  // Auto-reply fires when an inbound SMS arrives and no webhook is configured,
  // or as an immediate acknowledgment before your agent processes.
  //
  // await commune.phoneNumbers.update(phone.id, {
  //   friendlyName: 'Support Line',
  //   autoReply: 'Thanks! Our agent will reply within 1 hour.',
  // });
  // console.log('Auto-reply set');

  // ── Send an SMS ────────────────────────────────────────────────────────────
  // Replace with a real number you own for testing.
  const recipient = '+14155551234';

  console.log(`Sending test SMS to ${recipient} from ${phone.number}...`);
  const result = await commune.sms.send({
    to:              recipient,
    body:            'Hello from your Commune agent!',
    phone_number_id: phone.id,
  });
  console.log(`  Sent — message_id: ${result.message_id}`);
  console.log(`         thread_id:  ${result.thread_id}`);
  console.log(`         status:     ${result.status}`);
  console.log();

  // ── List conversations ─────────────────────────────────────────────────────
  console.log(`Conversations on ${phone.number}:`);
  const convos = await commune.sms.conversations({ phone_number_id: phone.id });

  if (convos.length === 0) {
    console.log('  No conversations yet.');
    return;
  }

  for (const c of convos) {
    console.log(`  ${c.remote_number}  (${c.message_count} messages)`);
    console.log(`    Last: ${c.last_message_preview}`);
    console.log(`    Thread: ${c.thread_id}`);
  }
  console.log();

  // ── Read a specific thread ─────────────────────────────────────────────────
  const first = convos[0];
  console.log(`Full thread with ${first.remote_number}:`);
  const msgs = await commune.sms.thread(first.remote_number, phone.id);

  for (const msg of msgs) {
    const dir = msg.direction === 'outbound' ? 'OUT' : ' IN';
    console.log(`  [${dir}] ${msg.created_at}  ${msg.content}`);
  }
}

main().catch(console.error);
