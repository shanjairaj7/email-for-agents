# SMS Quickstart: Send Your First Text in 60 Seconds

List your available phone numbers, send a test SMS, and print the delivery receipt. No server required.

```python
python quickstart.py
# Phone number: +14155552671
# SMS sent to +15551234567
# message_id=SM7a3c... thread_id=thr_9x2... status=queued credits_charged=1
```

---

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env — add your COMMUNE_API_KEY and TEST_PHONE_NUMBER
```

Get your API key at [commune.sh](https://commune.sh). Your test phone number is the real mobile number you want to text.

**3. Run**

```bash
python quickstart.py
```

For TypeScript:

```bash
npm install
npx tsx quickstart.ts
```

---

## .env.example contents

```
COMMUNE_API_KEY=comm_your_key_here
TEST_PHONE_NUMBER=+15551234567
```

---

## What's happening

1. `commune.phone_numbers.list()` — fetches all phone numbers on your Commune account. The first SMS-capable number is used automatically.
2. `commune.sms.send()` — sends the message and returns a receipt with `message_id`, `thread_id`, `status`, and `credits_charged`.
3. The receipt is printed so you can verify delivery before wiring up a full agent.

If you have no phone numbers yet, provision one from the [Commune dashboard](https://commune.sh) — it takes under a minute.
