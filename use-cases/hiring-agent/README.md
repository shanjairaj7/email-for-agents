# Hiring Agent

LangChain-based email responder for a hiring inbox.

Receives inbound emails from candidates, classifies their stage (new applicant, follow-up, scheduling request), and sends the appropriate reply — screening questionnaire, interview invite, or polite rejection.

## Stack

- LangChain for LLM reasoning
- Commune for inbound email webhook + threaded reply
- Flask for webhook endpoint

## File

`email_responder.py` — webhook handler + LangChain agent

## Run

```bash
pip install flask langchain langchain-openai commune-mail
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
export COMMUNE_WEBHOOK_SECRET=whsec_...
export COMMUNE_INBOX_ID=i_...
python email_responder.py
```

## Related

- [use-cases/hiring-and-recruiting/](../hiring-and-recruiting/) — full hiring pipeline examples
- [langchain/customer-support/](../../langchain/customer-support/) — same pattern for support
