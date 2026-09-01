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
🚧 **Phase 34 Path A ($0 Free Permanent) — merged api+worker + single Render Free service.** `services/core-api/app/main.py:34` `lifespan` now starts `worker.worker:130` as `asyncio.create_task` (fallback `app.worker`) — single `Free` web service handles both API and `RAG ingest` queue (no separate `worker` on `Free` tier, see `docs/DEPLOYMENT.md`). `services/core-api/Dockerfile:1` `context: .` (`COPY services/core-api/app ./app` + `COPY services/worker/app ./worker` + `alembic upgrade head` in `CMD`), `docker-compose.yml:40` `core-api` `context: .` with vendored `services/core-api/app/worker.py:1`. `render.yaml:1` stripped to 1 `plan: free` `nexora-core-api` with `DATABASE_URL`/`REDIS_URL` `sync: false` (Supabase `supabase/enable_pgvector.sql:3` + Upstash). Verified: `py_compile` `main.py`/`worker.py` ok, `yaml.safe_load(render.yaml)` ok, `docker compose config` ok.

**Phase 33 — CI + deploy smoke harness.** New `.github/workflows/ci.yml`: `backend` job (pgvector:pg16 + redis:7, `DATABASE_URL`/`REDIS_URL`, `alembic upgrade head`, `py_compile` five app modules, `pytest tests/ -v`, offline `rag_eval`), `frontend` job (`npm ci` + `npm run build` → 12 routes), `docker` job (`compose build core-api/web`). New `scripts/smoke.py` hits `GET /health` (`X-Request-ID`), `GET /metrics`, `GET /`, `GET /agents` public + `POST /agents/run` 401 guard, `POST /rag/search` 401, ephemeral `POST /auth/register→login→GET /agents`, and offline RAG eval — `python scripts/smoke.py --base http://localhost:8000` → 7 checks `PASS`. Verified: `yaml.safe_load` ok, `python scripts/smoke.py` `PASS`, `70/70` tests pass.

**Phase 32 — Observability (request-ID + Prometheus /metrics + structured logs).** New `app/middleware/request_id.py`: `RequestIdMiddleware` reuses inbound `X-Request-ID` or generates 12-hex, emits one JSON log per request (`level/method/path/status/duration_ms/request_id/user_id`) to stdout, and maintains in-memory counters (`nexora_http_requests_total`, `by_status`, `duration_ms_sum/count` normalized on `:id`). New `GET /metrics` (`app/routers/metrics.py`) exposes Prometheus text exposition (`version="0.2.0" phase="32"`). Verified: `curl /metrics` → text/plain, `X-Request-ID` header on every response (reuse test), `docker logs` JSON lines, 70/70 tests pass (4 new `test_metrics`), `core-api` rebuilt.

**Phase 31 — RAG chunk inspector page.** New `apps/web/src/app/rag/page.tsx`: score-sorted `POST /rag/search` inspector — query input, `top_k` selector, optional `document_id` filter, hybrid `α`/`rerank_enabled` echo, per-hit `distance` + `score` with percentage bar, `chunk_id`/`document_id` provenance, and empty-state tips. Linked from chat sidebar (`RAG`). Verified: `next build` 6.9s → 11 routes (new `/rag`), `tsc` clean, `GET /health` 200, `openapi.json` confirms `/rag/search`.

**Phase 30 — RAG inspector + eval CLI.** `POST /api/v1/rag/search` returns raw hybrid hits with `distance` + `score` (no LLM) — same `retrieve` as `rag/query` but without synthesis, plus `alpha`/`rerank_enabled` echo for the inspector UI. `POST /rag/query` citations now include `score`. CLI `scripts/rag_eval.py --offline|--live --fixture --user-id` wraps `evaluate_offline`/`evaluate_live` with human + `--json` output; demo: `python scripts/rag_eval.py --offline` → 3 cases `recall=0.50 mrr=0.67 hit_rate=0.67`. Verified: `openapi.json` lists `/rag/search`, `py_compile` clean, 66/66 tests pass, `core-api` rebuilt.

**Phase 29 — RAG golden-set eval harness.** New `app/rag/eval.py`: offline `score_case`/`_ndcg`/`load_golden` + `evaluate_offline` (pure-Python, no DB) and `evaluate_live` (calls `retrieve` per case). Metrics: recall, precision, MRR, NDCG, hit_rate + mean aggregates; fixture `tests/fixtures/rag_golden_small.json` (3 cases). 8 new `test_rag_eval` unit tests (perfect/partial/no-hit, empty-expected, validation, aggregate). Live mode reuses the same scoring after real retrieval — ready for `RAG_QUERY_REWRITE_ENABLED`/`α` A/B. Verified: 66/66 tests pass, `py_compile` clean.

**Phase 28 — Hybrid RAG (vector + keyword) + rerank + query rewrite.** `app/rag/service.py:retrieve` now over-fetches vector candidates (`top_k * multiplier`, max 20) and unions `ILIKE` keyword candidates (per-token, user/document scoped), then reranks via `score = α·(1−distance) + (1−α)·keyword_overlap` (BM25-ish token overlap, `α=RAG_HYBRID_ALPHA=0.6`). Keyword hits fix exact-term misses that pure embeddings drop (names, codes). Optional LLM query rewrite (`RAG_QUERY_REWRITE_ENABLED`, LITE tier) expands short queries before embedding; single-letter/stopword filtering via `_tokenize`. New settings `rag_hybrid_alpha`, `rag_candidate_multiplier`, `rag_rerank_enabled`, `rag_query_rewrite_enabled`. 8 new `test_rag_hybrid` unit tests. Verified: 58/58 tests pass, `py_compile` clean, `next build` 43s, `alembic upgrade head` idempotent, `core-api` rebuilt.

**Phase 27 — Builder streaming parity.** Workflow `POST /workflows/{id}/execute` now streams synthesis via `synthesize_final_answer_streaming` (`SYNTHESIS_DELTA`/`SYNTHESIS_DONE` on the same WS workflow channel that already drives node states) — parity with chat's Phase 25 streaming. Builder `Builder.tsx` renders live synthesis with blinking caret in the inspector (streaming while `executing`, persisted synthesis after `FINAL_RESPONSE_READY`). `useWorkflowStream` resets per-run state on workflowId change and handles `SYNTHESIS_DONE`. Verified: `tsc`/build clean, 50/50 tests pass, container rebuilt.

**Phase 26 — Real cost estimation.** New `app/llm/pricing.py`: `estimate_cost(provider, model, tokens_in, out)` computes USD from a model-substring → (input, output) $/1M-tok table (qwen/llama/gemma/gemini entries + wildcard fallback), overridable via env `LLM_COST_TABLE_JSON`. `record_usage` now writes real `estimated_cost` (was hardcoded 0). `/usage/summary` returns `est_cost_usd` totals + per-model; dashboard swaps cache-rate card for **Est. cost** and adds a cost column to the model table. Verified E2E: one chat run (245 in / 843 out tok) → `$0.000277` recorded and surfaced. 50/50 tests pass.

**Phase 25 — Token-by-token answer streaming.** `GroqProvider.generate_stream` (SSE) with stream-safe `<think>` filter across chunk boundaries; `SYNTHESIS_DELTA`/`SYNTHESIS_DONE` emitted on the workflow WS channel during multi-step chat runs (blocking-generate fallback + same 429 backoff); chat pending bubble renders synthesis live with blinking caret. Fixed latent `emit` NameError in `chat.py` failure path. Verified: 218 deltas matching persisted answer.

**Phase 23 — Usage/metrics dashboard.** New `GET /api/v1/usage/summary?days=N` (1–90, per-user scoped): totals (calls, cached, tokens in/out, avg latency), per-model breakdown (`GROUP BY provider,model`), and per-day buckets (`func.date(created_at)`) — all over the `api_usage` table that was already being written at ~20 call sites but never surfaced. `/dashboard` page renders it: stat cards (requests/tokens/latency/cache-hit-rate), pure-CSS daily bar chart with hover tooltips, per-model table, 7/14/30-day range switcher; linked from the chat sidebar ("Usage"). Verified E2E against real accumulated usage data (2 calls, qwen model row, day bucket correct); `tsc`/build clean; containers rebuilt.

**Phase 22 — Live streaming chat.** `/chat` no longer blocks: new `POST /chat/start` returns the plan (conversation_id, workflow_id, seed steps) in seconds while execution runs as a background task (`_execute_chat_workflow` in `routers/chat.py`: own `SessionFactory` session, never raises, always emits `FINAL_RESPONSE_READY`, persists an assistant message even on failure). The chat UI subscribes to the existing `WS /ws/workflows/{id}` stream: pending bubble shows live agent chips (spinner → check/cross per step), "Agents working…" while connected, plus a 4s polling fallback if the WS is unavailable — on completion it swaps in the persisted answer. Shared prep logic extracted (`_prepare_chat`/`_finalize_chat`/`_chat_response`); legacy blocking `POST /chat` kept working on the same code path. Verified E2E: `/chat/start` returned plan in **2.9s**, WS streamed `AGENT_COMPLETED(0)` + `FINAL_RESPONSE_READY`, assistant answer persisted ("George Orwell [1]").

**Phase 21 — Chat workspace UI.** `/chat` page (`ChatWorkspace.tsx`, dynamic `ssr:false`): conversation sidebar, thread bubbles, composer (Enter/Shift+Enter), minimal markdown renderer for reports, agent chips per answer via lazy workflow fetch (`workflow_id` now exposed on assistant messages via `MessageOut`). Planner provider failures fall back to single-step search instead of 500ing `/chat`.

**Phase 20 — Live Agent Network view.** Workflow execution streams live into the builder canvas: `useWorkflowStream` hook connects to `WS /api/v1/ws/workflows/{id}` and maps `AGENT_SELECTED/STARTED/COMPLETED/FAILED` + `WORKFLOW_*` events onto React Flow node states plus a LIVE header chip and activity timeline. Run flow: save fresh workflow → open WS → fire execute once connected (3s fallback). Backend emits `FINAL_RESPONSE_READY` after synthesis commits; ADR-0005 amended (WebSocket rationale).

**Phase 19 — Specialized agents (Research / Data / Writer).** `research-agent` (sub-questions → multi-search → cross-check → cited synthesis), `data-agent` (CSV/Excel via LLM-generated pandas in sandbox), `writer-agent` (structured markdown reports). Registered in registry + executor + `/agents/run` + builder palette (7 agents). CSV/XLSX/TXT upload allowlist; pandas+openpyxl; Groq `<think>` strip + 429 backoff; templates: Deep Research Report, CSV Analysis Report, Multi-Source Brief. Verified with real runs (6-source cited report; sandbox `exit_code=0` describe() output).

> **Deployment status:** ✅ **LIVE — Phase 35 Everything.** Backend `https://nexora-core-api.onrender.com` (`render.yaml:1` `plan: free` single `nexora-core-api` + merged `core-api+worker` `services/core-api/app/main.py:34` + Supabase `supabase/enable_pgvector.sql:3` + Upstash) and frontend `https://web-nine-snowy-57.vercel.app/` are deployed and verified 2026-09-01: `python scripts/smoke.py --base https://nexora-core-api.onrender.com` → **7/7 PASS** (`GET /health` + `X-Request-ID` `app/middleware/request_id.py:1`, `GET /metrics` `app/routers/metrics.py:26`, `GET /` + `GET /agents` 7 agents + `POST /agents/run` 401 + `POST /rag/search` 401 + `register→login→GET /agents` + offline RAG eval), plus live E2E `POST /chat/start` → workflow + `GET /usage/summary` + `GET /security/health` 98/100. Vercel `apps/web` builds 16 routes (`/projects` `app/models/project.py:6` + `/files` `/agents` `/security` `/marketplace` via `apps/web/src/components/app-shell.tsx:12` 10-link nav). Local still `docker compose` (`docker-compose.yml:40` `context: .` + `alembic 0009_projects` pending `upgrade head` on next Render deploy).

**Phase 35 — Everything (2026-09-01).** Backend `Project` `services/core-api/app/models/project.py:6` + `alembic 0009` + `app/routers/projects.py:14` CRUD (owner-scoped, `GET/POST/PATCH/DELETE`), mounted at `app/main.py:99`. Frontend 5 new product pages: `apps/web/src/app/projects/page.tsx`, `files/page.tsx` (`POST /documents` upload), `agents/page.tsx` (registry), `security/page.tsx` (`GET /security/health`), `marketplace/page.tsx` (templates). `next build` 5.5s → 16 routes. `py_compile` pass. Push → Render auto-mirrors `0009_projects` via `Dockerfile CMD alembic upgrade head`; Vercel auto-deploys `NEXT_PUBLIC_API_URL=https://nexora-core-api.onrender.com/api/v1` (`render.yaml:35` CORS allowlist already includes this Vercel URL).

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
