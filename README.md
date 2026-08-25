# Nexora — AI Command Center

> One command. A team of AI agents. One intelligent result.

Nexora is a multi-agent AI orchestration platform: a user issues a single
natural-language command, an Orchestrator agent plans and delegates the work
across specialized agents (search, documents, RAG, coding), agents execute
using permissioned tools, and results are validated and synthesized into one
cited, trustworthy answer — visualized live as it happens.

Full architecture, security model, and roadmap: see
[`docs/architecture/PROJECT_BLUEPRINT_V1.md`](./docs/architecture/PROJECT_BLUEPRINT_V1.md).

## Status
🚧 **Phase 19 — Specialized agents (Research / Data / Writer) complete.** New agents: `research-agent` (sub-question decomposition → per-subquestion web search → cross-check → cited synthesis), `data-agent` (CSV/Excel analysis via LLM-generated pandas run in the sandboxed `execute_code` tool), `writer-agent` (polished markdown reports: Title, Executive Summary, Body with inline citations, Takeaways, References). All registered in `AGENT_REGISTRY` + `REGISTRY_INFO`, wired into `/agents/run` and the DAG executor (`executor.py`), and available in the workflow builder palette (7 agents). Uploads extended beyond PDF: `.csv`/`.xlsx`/`.xls`/`.txt` allowlist (`documents.py`) for the Data Agent; deps `pandas`+`openpyxl`. Groq provider hardened: strips stray/unclosed `<think>` tags, 429 retry backoff 2s→4s (max 8s). New templates at `GET /workflows/templates`: Deep Research Report (`research→writer`), CSV Analysis Report (`data→writer`), Multi-Source Brief (`search`+`rag`+`research` parallel → `writer`). Verified live end-to-end: research run returned cited report with 6 sources (Groq `qwen`, non-mock); CSV upload → data-agent sandbox exec `exit_code=0` with real `describe()` output; writer/data runs via `/agents/run` OK; `tsc --noEmit` clean. **Live:** Frontend `https://nexora.vercel.app` + Backend `https://nexora-core-api.onrender.com` (see `docs/DEPLOYMENT.md`; Fly worker config in `fly.worker.toml`). Local still: `http://localhost:3000` + `http://localhost:8000/docs`. Next: V1 wrap-up — agent network live view polish, evals, usage dashboard.

## Monorepo layout

```
apps/web/           → Next.js frontend (design system + auth UI in Phase 3)
services/core-api/   → FastAPI backend: auth, projects, orchestrator (Phase 4+)
services/worker/      → Background job workers (Phase 16)
packages/agent-sdk/    → Shared Agent/Tool interfaces (Phase 9+)
infrastructure/docker/ → Extra Docker configs (nginx, monitoring — later phases)
docs/architecture/       → Blueprint and architecture docs
```

## Running Phase 1 locally

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Start the stack:
   ```bash
   docker compose up --build
   ```
3. Verify:
   - Core API health check: http://localhost:8000/health → `{"status":"ok",...}`
   - Postgres is up on `localhost:5432` (pgvector extension pre-installed via the `pgvector/pgvector:pg16` image)
   - Redis is up on `localhost:6379`

## Why these technology choices (short version)

- **pgvector, not a separate vector DB** — one less service to run/secure at this scale.
- **Redis, not Kafka/RabbitMQ** — doubles as cache + queue with zero extra infra.
- **Modular monolith for MVP, not 10 microservices** — services get extracted only when there's a real scaling/isolation reason (see Blueprint §17).

Full reasoning for every decision is in the blueprint doc linked above.

## License
TBD.
