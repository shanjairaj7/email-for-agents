# Your Personal AI That Texts You Back

A personal AI assistant with a real phone number. It texts you a morning summary every day at 9am, and replies to any text you send it within seconds.

```
You: "What should I work on today?"
Agent: "Top 3: finish the API docs, reply to Sarah's email, prep for 3pm standup."

You: "Remind me to call mom at 6pm"
Agent: "Got it — I'll text you at 6pm: call mom."

[9:00am, unprompted]
Agent: "Morning! Today: dentist at 2pm, team sync at 4pm. Reply with anything."
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
# Fill in all variables — especially MY_PHONE_NUMBER (your personal cell)
```

**3. Expose your server (local dev)**

```bash
ngrok http 8000
# Set this URL as your webhook in the Commune dashboard
```

**4. Register the webhook**

In the Commune dashboard, set your phone number's webhook to `https://your-url.ngrok.io/webhook/sms`.

**5. Run**

```bash
python agent.py
```

The agent starts a background thread for the morning summary and a Flask server for responding to texts. Both run in the same process.

---

## .env.example contents

```
COMMUNE_API_KEY=comm_your_key_here
OPENAI_API_KEY=sk-your_openai_key_here
PHONE_NUMBER_ID=pn_your_phone_number_id_here
MY_PHONE_NUMBER=+15551234567
OWNER_NAME=Alex
TIMEZONE=US/Eastern
```

---

## What's happening

**Security:** The webhook only responds to texts from `MY_PHONE_NUMBER`. Texts from anyone else are silently ignored. This means the agent is exclusively yours.

**Conversation memory:** Every text you send and every reply the agent gives is stored in Commune's conversation thread. When you text again, the agent fetches the last 20 messages as context — so it remembers what you talked about.

**Morning summary:** A background thread checks the time every 30 seconds. At 9:00am in your local time, it sends a morning check-in. You can customize this to pull from a calendar file, a todo list, or any API you have access to.

**Proactive vs reactive:** The agent runs both modes in the same process. The background thread handles proactive outreach; the Flask server handles reactive replies. You can deploy this to a server (Railway, Fly, etc.) and leave it running permanently.

**Keeping responses short:** The system prompt instructs GPT-4o-mini to keep replies under 160 characters when possible. You can remove this constraint if you're okay with multi-segment messages.
