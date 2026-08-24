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
🚧 **Phase 18 — Workflow Builder (React Flow) complete.** Backend `POST /api/v1/workflows` (steps `agent_id/instruction/depends_on` + `definition` nodes/edges, 8-step cap, DAG validation), `GET /workflows`/`/templates` (3 templates: Research+RAG, PDF Summary, Code Run), `POST /workflows/{id}/execute` (reset → parallel `execute_workflow` → `synthesize`, `definition.synthesis`). Frontend `@xyflow/react` canvas (`/workflows` list + `/workflows/builder` with palette (Search/RAG/PDF/Code), drag/drop, handles for edges → `depends_on`, inspector for instruction/agent, `definition` persistence, Save/Run/Clear). Auth wired (`login`/`register` store `access_token` → `localStorage`, `apiFetch` adds `Authorization`). Verified live: `templates` 3, `POST /workflows` 2 parallel steps `planning`, `execute` → `done` 2 steps (`search`+`rag`) + `synthesis`, `GET /workflows` 1, web `/workflows` + `/workflows/builder` 200. Next: Research/Data/Writer agents (V1) — Phase 19.

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
