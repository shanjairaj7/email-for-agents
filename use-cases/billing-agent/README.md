# Billing Agent

CrewAI multi-agent crew for processing inbound invoice emails.

Receives invoices from vendors, extracts line items and totals, validates them against expected amounts, and sends a confirmation or dispute reply.

## Stack

- CrewAI for multi-agent orchestration
- Commune for inbound email webhook + reply
- Flask for webhook endpoint

## File

`invoice_crew.py` — webhook handler + CrewAI crew definition

## Run

```bash
pip install flask crewai crewai-tools commune-mail
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
export COMMUNE_WEBHOOK_SECRET=whsec_...
export COMMUNE_INBOX_ID=i_...
python invoice_crew.py
```

## Related

- [crewai/support-crew/](../../crewai/support-crew/) — general CrewAI support pattern
- [ADR-003](../../adr/003-extraction-schemas-over-llm-parsing.md) — structured extraction for invoice fields
