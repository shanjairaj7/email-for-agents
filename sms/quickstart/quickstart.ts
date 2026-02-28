/**
 * SMS Quickstart — send your first text in 60 seconds (TypeScript).
 *
 * Steps:
 *   1. List phone numbers to find one with SMS capability
 *   2. Send a test SMS to TEST_PHONE_NUMBER
 *   3. Print the delivery receipt
 *
 * Usage:
 *   npx tsx quickstart.ts
 */

import { CommuneClient } from "commune-ai";
import * as dotenv from "dotenv";

dotenv.config();

// Validate required environment variables before doing anything else.
const required = ["COMMUNE_API_KEY", "TEST_PHONE_NUMBER"];
for (const varName of required) {
  if (!process.env[varName]) {
    console.error(
      `Missing env var: ${varName} — copy .env.example to .env and fill it in.`
    );
    process.exit(1);
  }
}

const API_KEY = process.env.COMMUNE_API_KEY!;
const TEST_PHONE = process.env.TEST_PHONE_NUMBER!;

const commune = new CommuneClient({ apiKey: API_KEY });

async function findSmsCapableNumber() {
  const numbers = await commune.phoneNumbers.list();

  if (!numbers || numbers.length === 0) {
    console.error(
      "No phone numbers found on your account. " +
        "Provision one at https://commune.sh before running this script."
    );
    process.exit(1);
  }

  // Use the first number that has SMS enabled
  for (const number of numbers) {
    if (number.capabilities?.sms) {
      return number;
    }
  }

  console.error(
    "No SMS-capable phone numbers found. " +
      "Check your Commune dashboard and ensure at least one number has SMS enabled."
  );
  process.exit(1);
}

async function main(): Promise<void> {
  console.log("Fetching phone numbers...");
  const phone = await findSmsCapableNumber();
  console.log(`Using phone number: ${phone.number}  (id=${phone.id})`);

  console.log(`\nSending SMS to ${TEST_PHONE}...`);

  let result;
  try {
    result = await commune.sms.send({
      to: TEST_PHONE,
      body: "Hello from Commune! Your SMS quickstart is working.",
      phoneNumberId: phone.id,
    });
  } catch (err) {
    console.error("SMS send failed:", err);
    process.exit(1);
  }

  // Print the full delivery receipt so you can verify everything looks right.
  console.log("\nDelivery receipt:");
  console.log(`  message_id      = ${result.messageId}`);
  console.log(`  thread_id       = ${result.threadId}`);
  console.log(`  status          = ${result.status}`);
  console.log(`  credits_charged = ${result.creditsCharged}`);
  console.log(`  segments        = ${result.segments}`);
  console.log("\nDone. Check your phone for the message.");
}

main().catch((err) => {
  console.error("Unexpected error:", err);
  process.exit(1);
});
