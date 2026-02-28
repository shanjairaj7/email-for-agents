# Phone Number for Your Hiring Agent: Dispatch Workers via SMS

An AI hiring agent that texts workers about open shifts, collects YES/NO confirmations, and emails the manager when all shifts are filled.

```
python agent.py dispatch   → texts all workers in shifts.json
python agent.py webhook    → starts webhook server to receive replies
```

---

## How it works

**Dispatch mode** reads `shifts.json`, checks the suppression list (workers who opted out via STOP), and sends a personalized SMS to every eligible worker. Responses are saved to `shift_status.json`.

**Webhook mode** listens for inbound SMS replies. Workers respond YES or NO. The agent:
- Confirms the worker and saves their status
- Sends a follow-up if the reply is ambiguous
- Emails the manager via Commune when all required confirmations are received

---

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Fill in all variables
```

**3. Edit shifts.json**

Add your open shifts and workers. See the sample in this folder.

**4. Expose your server (local dev)**

```bash
ngrok http 8000
# Set this URL as your webhook in the Commune dashboard
```

**5. Dispatch offers**

```bash
python agent.py dispatch
```

**6. Start webhook server to receive replies**

```bash
python agent.py webhook
```

Run both in separate terminals, or deploy the webhook mode to a server.

---

## .env.example contents

```
COMMUNE_API_KEY=comm_your_key_here
PHONE_NUMBER_ID=pn_your_phone_number_id_here
COMMUNE_INBOX_ID=inbox_your_inbox_id_here
MANAGER_EMAIL=manager@yourcompany.com
REQUIRED_CONFIRMATIONS=2
```

---

## What's happening

**Suppression check:** Before every send, the agent calls `commune.sms.suppressions()` to get the current opt-out list. Workers who sent STOP are skipped automatically — this is both legally required and good practice.

**Rate limiting:** A 0.5-second delay between sends prevents carrier rate limiting. For large batches (100+ workers), increase this to 1–2 seconds.

**Status tracking:** `shift_status.json` persists the state across restarts. If the webhook server goes down and comes back up, it picks up where it left off.

**Manager notification:** When confirmed workers reach `REQUIRED_CONFIRMATIONS`, the agent sends a summary email via `commune.messages.send()`. This closes the loop without requiring the manager to monitor the dashboard.

**Opt-out safety:** Workers can always reply STOP to opt out. Commune handles the suppression automatically — this agent just respects that list on the send side.
