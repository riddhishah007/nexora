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
🚧 **Phase 9 — Orchestrator skeleton complete.** `POST /api/v1/chat` now runs
the full loop: LLM planner decomposes the message into a step DAG
(`workflow_steps`), a sequential executor walks the DAG and dispatches
registered agents, results persist to `conversations`/`messages`/`workflows`.
With real keys the planner emits genuine multi-step plans; mock fallbacks
keep dev verifiable offline. Next: Tool system registry (Phase 10).

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
