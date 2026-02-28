# SMS Marketing Campaigns for AI Agents

Send personalized SMS campaigns to your contact list, follow up with non-responders, and track response rates — all from the command line.

```bash
python campaign.py broadcast "Hi {name}, we thought you'd love our new product!"
python campaign.py drip        # follow up with non-responders after 48h
python campaign.py status      # show response rates
```

---

## Quickstart

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Fill in COMMUNE_API_KEY, OPENAI_API_KEY, PHONE_NUMBER_ID
```

**3. Add your contacts**

Edit `contacts.csv` — one row per contact. The agent personalizes each message using the contact's name, company, and role fields.

**4. Send the campaign**

```bash
python campaign.py broadcast "Hi {name}, wanted to share something you'll love."
```

**5. Follow up with non-responders (48 hours later)**

```bash
python campaign.py drip
```

**6. Check response rates**

```bash
python campaign.py status
```

---

## .env.example contents

```
COMMUNE_API_KEY=comm_your_key_here
OPENAI_API_KEY=sk-your_openai_key_here
PHONE_NUMBER_ID=pn_your_phone_number_id_here
CAMPAIGN_NAME=Spring Campaign
```

---

## Compliance

SMS marketing is regulated. Before sending:

**STOP/START handling:** Commune automatically processes STOP and START replies and maintains your suppression list. The broadcast mode checks `commune.sms.suppressions()` before every send and skips opted-out contacts.

**A2P 10DLC (US):** If you're sending marketing messages from a 10-digit long code (local number), you must register your brand and campaign with The Campaign Registry. This applies to US sending. Toll-free numbers have a separate verification process. See [commune.sh/docs](https://commune.sh/docs) for registration steps.

**Consent:** Only message contacts who have opted in to receive SMS from you. Unsolicited marketing SMS is a legal liability and will get your number flagged by carriers.

**Send rate:** The broadcast mode adds a 1-second delay between sends by default. For large lists (1,000+), increase this or use a registered toll-free number which supports higher throughput.

---

## Drip sequences

The `drip` mode finds contacts who received an outbound message but haven't replied after 48 hours, then sends a follow-up. It caps at 10 follow-ups per run to avoid overwhelming anyone.

To build a full multi-step drip sequence, schedule `python campaign.py drip` as a cron job:

```bash
# Run drip check every 24 hours
0 10 * * * cd /path/to/sms-marketing && python campaign.py drip
```

---

## Personalization

The broadcast mode uses GPT-4o-mini to personalize each message based on the contact's name, company, and role from `contacts.csv`. This produces natural, human-sounding messages rather than obvious mail-merge substitutions.

To disable AI personalization and use the template literally (with `{name}` substituted), remove the `personalize_message()` call and use `template.replace("{name}", contact.get("name", "there"))` instead.

---

## What's happening

1. **broadcast**: Reads `contacts.csv`, fetches suppression list, personalizes the template via GPT-4o-mini for each contact, sends via `commune.sms.send()`, and prints a summary.
2. **drip**: Calls `commune.sms.conversations()` to find threads where only one message was sent (no reply), filters to those older than 48 hours, and sends a follow-up to each.
3. **status**: Calls `commune.sms.conversations()` and counts threads with more than one message as "replied", reporting the response rate.
