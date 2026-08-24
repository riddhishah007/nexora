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
🚧 **Phase 17 — Security layer complete.** `security_events` + `audit_logs` tables (alembic `0008`), injection detector (16 regex, score→`critical` block, `medium` log), `is_url_allowed` SSRF guard (`private/metadata` + DNS public-IP check) + `url_blocked`/`ssrf_blocked` events, `permission_denied` + `data_isolation_violation` (FK-safe), `failed_login` (auth). `POST /api/v1/chat` scans before planner (400 on `critical`/`high`, log otherwise), `fetch_page` blocks `localhost`/`169.254`/`192.168`. `GET /api/v1/security/{events,audit,health}` (health = 4 dims `auth/api/agent_permissions/data_isolation` 100−deductions, `blocked_24h`/`total_7d`). Verified live: `chat` normal `done`, injection `Pretend you are hacker` → `400 risk=high`, `failed_login` → `401`, `fetch_page http://localhost` → `blocked`, `example.com` → `ok`, health `83 blocked 6`, events 5 latest `critical`. Next: Workflow Builder UI (React Flow) — Phase 18.

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
