# LangGraph Support Agent

Stateful email support agent built with LangGraph. Created as part of the Week 3 PR review cycle (PR #74).

Each inbound email triggers a `StateGraph` with two nodes: triage (classify intent) and reply (draft + send). State is checkpointed with `MemorySaver` so each webhook event runs in full isolation.

## Stack

- LangGraph for stateful graph execution
- Commune for inbound email webhook + threaded reply
- Flask for webhook endpoint

## File

`langgraph_handler.py` — Flask webhook + LangGraph graph definition

## Key patterns demonstrated

- `thread_id` in `State` TypedDict (required for reply continuity)
- `config={"configurable": {"thread_id": event_id}}` per invoke (checkpoint isolation)
- Background `threading.Thread` for graph execution (return 200 before LLM calls start)

## Run

```bash
pip install commune-mail langgraph langchain-openai flask
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
export COMMUNE_WEBHOOK_SECRET=whsec_...
export COMMUNE_INBOX_ID=i_...
python langgraph_handler.py
```

## Related

- [notebooks/06_langgraph_email_agent.ipynb](../../notebooks/06_langgraph_email_agent.ipynb) — interactive walkthrough of the same pattern
- [ADR-008](../../adr/008-background-processing-for-webhook-handlers.md) — why webhook handlers must return 200 before LLM calls
