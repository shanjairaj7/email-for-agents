# Give Your AI Agent Its Own Phone Number

A Flask webhook server that gives an AI agent a dedicated SMS line. When someone texts the agent's number, it fetches the full conversation history, passes it to GPT-4o-mini, and replies — all within a few seconds.

```
User texts +1 415 555 0100
        ↓
Commune webhook → POST /webhook/sms
        ↓
commune.sms.thread() → conversation history
        ↓
GPT-4o-mini → generates reply
        ↓
commune.sms.send() → user receives reply
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
# Fill in COMMUNE_API_KEY, OPENAI_API_KEY, PHONE_NUMBER_ID
```

Get your Commune API key at [commune.sh](https://commune.sh). Find your `PHONE_NUMBER_ID` in the Commune dashboard under Phone Numbers.

**3. Expose your server (local dev)**

```bash
ngrok http 8000
# Copy the https URL, e.g. https://abc123.ngrok.io
```

**4. Register the webhook in Commune dashboard**

Set your webhook URL to: `https://abc123.ngrok.io/webhook/sms`

**5. Run the agent**

```bash
python agent.py
```

**6. Test it**

Text your Commune phone number. The agent will reply within a few seconds.

---

## .env.example contents

```
COMMUNE_API_KEY=comm_your_key_here
OPENAI_API_KEY=sk-your_openai_key_here
PHONE_NUMBER_ID=pn_your_phone_number_id_here
```

---

## What's happening

1. Inbound SMS hits `POST /webhook/sms`. The payload includes `from_number`, `body`, and `thread_id`.
2. `commune.sms.thread()` fetches the full conversation history between this sender and your number. This gives the LLM real context — it can reference earlier messages.
3. The last 10 messages are formatted into an OpenAI `messages` array, with `inbound` mapped to `"user"` and `outbound` mapped to `"assistant"`.
4. GPT-4o-mini generates a reply. The system prompt tells it to keep responses under 160 characters (one SMS segment).
5. `commune.sms.send()` delivers the reply back to the sender.

**Conversation history window:** The agent uses the last 10 messages to keep token usage predictable. Increase this if your use case requires longer memory.

**Production note:** Add HMAC signature verification before deploying publicly. The code includes a stub comment showing exactly where to add it.
