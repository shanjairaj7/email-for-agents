# LangChain Thread Patterns

Production patterns for managing email threads in LangChain agents — the things that break in real deployments but not in tutorials.

## Notebook

[`thread_patterns.ipynb`](thread_patterns.ipynb) — run in Colab or locally with `jupyter lab`

## What's covered

- **Thread ID propagation** — capturing `thread_id` from webhook payloads and passing it through to replies; what breaks when you omit it
- **Contrastive pairs** — side-by-side correct vs. incorrect implementations with real API responses showing the difference
- **Context window management** — truncating thread history for long conversations without losing critical context
- **Idempotency** — preventing duplicate sends when LangChain retries tool calls

## Run locally

```bash
pip install jupyter commune-mail langchain langchain-openai
export COMMUNE_API_KEY=comm_...
export OPENAI_API_KEY=sk-...
jupyter lab thread_patterns.ipynb
```

## Related

- [../customer-support/](../customer-support/) — full support agent that applies these patterns
- [ADR-001](../../adr/001-use-thread-id-for-all-replies.md) — why thread_id matters
- [ADR-006](../../adr/006-idempotency-keys-for-agent-email-sends.md) — idempotency for sends
