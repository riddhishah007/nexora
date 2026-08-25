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
🚧 **Phase 21 — Chat workspace UI complete.** `/chat` page (`ChatWorkspace.tsx`, dynamic `ssr:false` like the builder): conversation sidebar (`GET /conversations`, New chat), message thread (user/assistant bubbles), composer (Enter to send, Shift+Enter newline), pending "Planning · running agents · synthesizing…" indicator, and a minimal markdown renderer (code fences, headings, lists, bold, inline code) for writer-agent reports. Each assistant answer shows agent chips (seq, agent_id, status color) by lazily fetching its workflow — backend now exposes `workflow_id` on assistant messages (`MessageOut`). Orchestrator hardened: planner provider failures (transient Groq 4xx/5xx observed in the wild) now fall back to a valid single-step search plan instead of 500ing `/chat` (`planner.py`). Verified live E2E: `POST /chat` → plan `[0 search-agent done]` → cited assistant answer persisted with `workflow_id`; conversation detail returns both messages; `tsc` + `next build` clean; web container rebuilt, `/chat` serves 200.

**Phase 20 — Live Agent Network view.** Workflow execution streams live into the builder canvas: `useWorkflowStream` hook connects to `WS /api/v1/ws/workflows/{id}` and maps `AGENT_SELECTED/STARTED/COMPLETED/FAILED` + `WORKFLOW_*` events onto React Flow node states plus a LIVE header chip and activity timeline. Run flow: save fresh workflow → open WS → fire execute once connected (3s fallback). Backend emits `FINAL_RESPONSE_READY` after synthesis commits; ADR-0005 amended (WebSocket rationale).

**Phase 19 — Specialized agents (Research / Data / Writer).** `research-agent` (sub-questions → multi-search → cross-check → cited synthesis), `data-agent` (CSV/Excel via LLM-generated pandas in sandbox), `writer-agent` (structured markdown reports). Registered in registry + executor + `/agents/run` + builder palette (7 agents). CSV/XLSX/TXT upload allowlist; pandas+openpyxl deps; Groq `<think>` strip + 429 backoff; templates: Deep Research Report, CSV Analysis Report, Multi-Source Brief. Verified with real runs (6-source cited report; sandbox `exit_code=0` describe() output). **Live:** Frontend `https://nexora.vercel.app` + Backend `https://nexora-core-api.onrender.com` (see `docs/DEPLOYMENT.md`; Fly worker config in `fly.worker.toml`). Local still: `http://localhost:3000` + `http://localhost:8000/docs`. Next: usage/metrics dashboard (`api_usage` recorded at ~20 call sites, no aggregation endpoint/UI yet), test suite + evals (zero tests today), streaming chat responses.

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
