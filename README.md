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
🚧 **Phase 22 — Live streaming chat.** `/chat` no longer blocks: new `POST /chat/start` returns the plan (conversation_id, workflow_id, seed steps) in seconds while execution runs as a background task (`_execute_chat_workflow` in `routers/chat.py`: own `SessionFactory` session, never raises, always emits `FINAL_RESPONSE_READY`, persists an assistant message even on failure). The chat UI subscribes to the existing `WS /ws/workflows/{id}` stream: pending bubble shows live agent chips (spinner → check/cross per step), "Agents working…" while connected, plus a 4s polling fallback if the WS is unavailable — on completion it swaps in the persisted answer. Shared prep logic extracted (`_prepare_chat`/`_finalize_chat`/`_chat_response`); legacy blocking `POST /chat` kept working on the same code path. Verified E2E: `/chat/start` returned plan in **2.9s**, WS streamed `AGENT_COMPLETED(0)` + `FINAL_RESPONSE_READY`, assistant answer persisted ("George Orwell [1]").

**Phase 21 — Chat workspace UI.** `/chat` page (`ChatWorkspace.tsx`, dynamic `ssr:false`): conversation sidebar, thread bubbles, composer (Enter/Shift+Enter), minimal markdown renderer for reports, agent chips per answer via lazy workflow fetch (`workflow_id` now exposed on assistant messages via `MessageOut`). Planner provider failures fall back to single-step search instead of 500ing `/chat`.

**Phase 20 — Live Agent Network view.** Workflow execution streams live into the builder canvas: `useWorkflowStream` hook connects to `WS /api/v1/ws/workflows/{id}` and maps `AGENT_SELECTED/STARTED/COMPLETED/FAILED` + `WORKFLOW_*` events onto React Flow node states plus a LIVE header chip and activity timeline. Run flow: save fresh workflow → open WS → fire execute once connected (3s fallback). Backend emits `FINAL_RESPONSE_READY` after synthesis commits; ADR-0005 amended (WebSocket rationale).

**Phase 19 — Specialized agents (Research / Data / Writer).** `research-agent` (sub-questions → multi-search → cross-check → cited synthesis), `data-agent` (CSV/Excel via LLM-generated pandas in sandbox), `writer-agent` (structured markdown reports). Registered in registry + executor + `/agents/run` + builder palette (7 agents). CSV/XLSX/TXT upload allowlist; pandas+openpyxl; Groq `<think>` strip + 429 backoff; templates: Deep Research Report, CSV Analysis Report, Multi-Source Brief. Verified with real runs (6-source cited report; sandbox `exit_code=0` describe() output). **Live:** Frontend `https://nexora.vercel.app` + Backend `https://nexora-core-api.onrender.com` (see `docs/DEPLOYMENT.md`; Fly worker config in `fly.worker.toml`). Local: `http://localhost:3000` + `http://localhost:8000/docs`. Next: usage/metrics dashboard (`api_usage` recorded at ~20 call sites, no aggregation endpoint/UI yet), test suite + evals (zero tests today), token-by-token answer streaming.

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
