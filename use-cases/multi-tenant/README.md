# Multi-Tenant Email Router

FastAPI router that dispatches inbound emails to per-tenant AI agents.

Each tenant gets an isolated inbox. The router reads the `inboxId` from the webhook payload, looks up the tenant's configuration, and dispatches to the correct agent — ensuring tenant A's emails never reach tenant B's agent.

## Stack

- FastAPI + uvicorn for the webhook endpoint
- Commune for inbound email + per-tenant inboxes
- OpenAI for per-tenant LLM calls

## File

`tenant_router.py` — FastAPI app + routing logic

## Run

```bash
pip install fastapi uvicorn openai commune-mail
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
export COMMUNE_WEBHOOK_SECRET=whsec_...
uvicorn tenant_router:app --port 8080
```

## Pattern

```
inbound email → Commune webhook → router reads inboxId
                                        ↓
                          tenant_config = TENANT_MAP[inboxId]
                                        ↓
                          agent(tenant_config).handle(email)
```

One webhook endpoint handles all tenants. Isolation is enforced by routing only to the agent that owns that inbox.

## Related

- [ADR-004](../../adr/004-one-inbox-per-agent-identity.md) — one inbox per agent identity
- [typescript/multi-agent/](../../typescript/multi-agent/) — TypeScript version of multi-agent routing
