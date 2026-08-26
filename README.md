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
🚧 **Phase 28 — Hybrid RAG (vector + keyword) + rerank + query rewrite.** `app/rag/service.py:retrieve` now over-fetches vector candidates (`top_k * multiplier`, max 20) and unions `ILIKE` keyword candidates (per-token, user/document scoped), then reranks via `score = α·(1−distance) + (1−α)·keyword_overlap` (BM25-ish token overlap, `α=RAG_HYBRID_ALPHA=0.6`). Keyword hits fix exact-term misses that pure embeddings drop (names, codes). Optional LLM query rewrite (`RAG_QUERY_REWRITE_ENABLED`, LITE tier) expands short queries before embedding; single-letter/stopword filtering via `_tokenize`. New settings `rag_hybrid_alpha`, `rag_candidate_multiplier`, `rag_rerank_enabled`, `rag_query_rewrite_enabled`. 8 new `test_rag_hybrid` unit tests. Verified: 58/58 tests pass, `py_compile` clean, `next build` 43s, `alembic upgrade head` idempotent, `core-api` rebuilt.

**Phase 27 — Builder streaming parity.** Workflow `POST /workflows/{id}/execute` now streams synthesis via `synthesize_final_answer_streaming` (`SYNTHESIS_DELTA`/`SYNTHESIS_DONE` on the same WS workflow channel that already drives node states) — parity with chat's Phase 25 streaming. Builder `Builder.tsx` renders live synthesis with blinking caret in the inspector (streaming while `executing`, persisted synthesis after `FINAL_RESPONSE_READY`). `useWorkflowStream` resets per-run state on workflowId change and handles `SYNTHESIS_DONE`. Verified: `tsc`/build clean, 50/50 tests pass, container rebuilt.

**Phase 26 — Real cost estimation.** New `app/llm/pricing.py`: `estimate_cost(provider, model, tokens_in, out)` computes USD from a model-substring → (input, output) $/1M-tok table (qwen/llama/gemma/gemini entries + wildcard fallback), overridable via env `LLM_COST_TABLE_JSON`. `record_usage` now writes real `estimated_cost` (was hardcoded 0). `/usage/summary` returns `est_cost_usd` totals + per-model; dashboard swaps cache-rate card for **Est. cost** and adds a cost column to the model table. Verified E2E: one chat run (245 in / 843 out tok) → `$0.000277` recorded and surfaced. 50/50 tests pass.

**Phase 25 — Token-by-token answer streaming.** `GroqProvider.generate_stream` (SSE) with stream-safe `<think>` filter across chunk boundaries; `SYNTHESIS_DELTA`/`SYNTHESIS_DONE` emitted on the workflow WS channel during multi-step chat runs (blocking-generate fallback + same 429 backoff); chat pending bubble renders synthesis live with blinking caret. Fixed latent `emit` NameError in `chat.py` failure path. Verified: 218 deltas matching persisted answer.

**Phase 23 — Usage/metrics dashboard.** New `GET /api/v1/usage/summary?days=N` (1–90, per-user scoped): totals (calls, cached, tokens in/out, avg latency), per-model breakdown (`GROUP BY provider,model`), and per-day buckets (`func.date(created_at)`) — all over the `api_usage` table that was already being written at ~20 call sites but never surfaced. `/dashboard` page renders it: stat cards (requests/tokens/latency/cache-hit-rate), pure-CSS daily bar chart with hover tooltips, per-model table, 7/14/30-day range switcher; linked from the chat sidebar ("Usage"). Verified E2E against real accumulated usage data (2 calls, qwen model row, day bucket correct); `tsc`/build clean; containers rebuilt.

**Phase 22 — Live streaming chat.** `/chat` no longer blocks: new `POST /chat/start` returns the plan (conversation_id, workflow_id, seed steps) in seconds while execution runs as a background task (`_execute_chat_workflow` in `routers/chat.py`: own `SessionFactory` session, never raises, always emits `FINAL_RESPONSE_READY`, persists an assistant message even on failure). The chat UI subscribes to the existing `WS /ws/workflows/{id}` stream: pending bubble shows live agent chips (spinner → check/cross per step), "Agents working…" while connected, plus a 4s polling fallback if the WS is unavailable — on completion it swaps in the persisted answer. Shared prep logic extracted (`_prepare_chat`/`_finalize_chat`/`_chat_response`); legacy blocking `POST /chat` kept working on the same code path. Verified E2E: `/chat/start` returned plan in **2.9s**, WS streamed `AGENT_COMPLETED(0)` + `FINAL_RESPONSE_READY`, assistant answer persisted ("George Orwell [1]").

**Phase 21 — Chat workspace UI.** `/chat` page (`ChatWorkspace.tsx`, dynamic `ssr:false`): conversation sidebar, thread bubbles, composer (Enter/Shift+Enter), minimal markdown renderer for reports, agent chips per answer via lazy workflow fetch (`workflow_id` now exposed on assistant messages via `MessageOut`). Planner provider failures fall back to single-step search instead of 500ing `/chat`.

**Phase 20 — Live Agent Network view.** Workflow execution streams live into the builder canvas: `useWorkflowStream` hook connects to `WS /api/v1/ws/workflows/{id}` and maps `AGENT_SELECTED/STARTED/COMPLETED/FAILED` + `WORKFLOW_*` events onto React Flow node states plus a LIVE header chip and activity timeline. Run flow: save fresh workflow → open WS → fire execute once connected (3s fallback). Backend emits `FINAL_RESPONSE_READY` after synthesis commits; ADR-0005 amended (WebSocket rationale).

**Phase 19 — Specialized agents (Research / Data / Writer).** `research-agent` (sub-questions → multi-search → cross-check → cited synthesis), `data-agent` (CSV/Excel via LLM-generated pandas in sandbox), `writer-agent` (structured markdown reports). Registered in registry + executor + `/agents/run` + builder palette (7 agents). CSV/XLSX/TXT upload allowlist; pandas+openpyxl; Groq `<think>` strip + 429 backoff; templates: Deep Research Report, CSV Analysis Report, Multi-Source Brief. Verified with real runs (6-source cited report; sandbox `exit_code=0` describe() output).

> **Deployment status:** not deployed yet — everything currently runs locally via `docker compose` (`http://localhost:3000` web, `http://localhost:8000/docs` API). Deployment configs are prepped for later: `docs/DEPLOYMENT.md`, `render.yaml`, `fly.worker.toml`. Next up: RAG golden-set evals (needs real embeddings with metrics), filtering/sorting UI for retrieved chunks.

## Monorepo layout

```
apps/web/           → Next.js frontend (design system + auth UI in Phase 3)
services/core-api/   → FastAPI backend: auth, projects, orchestrator (Phase 4+)
services/worker/      → Background job workers (Phase 16)
packages/agent-sdk/    → Shared Agent/Tool interfaces (Phase 9+)
infrastructure/docker/ → Extra Docker configs (nginx, monitoring — later phases)
docs/architecture/       → Blueprint and architecture docs
```

## Running locally

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Start the stack:
   ```bash
   docker compose up --build
   ```
3. Verify:
   - Web: http://localhost:3000
   - Core API health check: http://localhost:8000/health → `{"status":"ok",...}`
   - Postgres is up on `localhost:5432` (pgvector extension pre-installed via the `pgvector/pgvector:pg16` image)
   - Redis is up on `localhost:6379`

## Running tests

Backend suite (unit tests run anywhere inside the container; `integration`-marked tests hit the live local stack and auto-skip when it's down):

```bash
docker exec nexora-core-api pip install -q -r requirements-dev.txt
docker exec -w /app nexora-core-api python -m pytest tests/ -v
```

Covered today: injection scanner, planner parsing + provider-failure fallback, Groq `<think>` stripping, upload filename sanitization/allowlists, plus API integration (health, auth roundtrip, agent registry shape, templates, workflow CRUD/validation, usage summary shape + user scoping, auth boundaries).

## Why these technology choices (short version)

- **pgvector, not a separate vector DB** — one less service to run/secure at this scale.
- **Redis, not Kafka/RabbitMQ** — doubles as cache + queue with zero extra infra.
- **Modular monolith for MVP, not 10 microservices** — services get extracted only when there's a real scaling/isolation reason (see Blueprint §17).

Full reasoning for every decision is in the blueprint doc linked above.

## License
TBD.
