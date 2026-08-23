# NEXORA

> **One Command. Many Agents. One Intelligent Result.**

Nexora is an AI Command Center where a central orchestrator plans your request, selects
specialized agents from a registry, executes them with real tools (search, RAG, code
sandbox), and streams the entire execution live to your screen — delivering one
intelligent, cited result.

**Status:** Phase 0 — Repository & Product Definition · [Blueprint](docs/BLUEPRINT.md) · [ADRs](docs/adr/)

## What it does

```
USER COMMAND
     │
     ▼
ORCHESTRATOR ──► plans task ──► selects agents from registry
     │
     ├──► Search Agent ──┐
     ├──► RAG Agent      ├──► validated outputs ──► SYNTHESIS ──► ANSWER + CITATIONS
     ├──► Coding Agent   │        (schemas,              (streamed live
     └──► Security Agent ┘         permissions)            via SSE)
```

## Core principles

- **Security-first** — prompt-injection defense, agent permission matrix, sandboxed code execution, tenant isolation
- **Visible orchestration** — the agent network UI renders real backend events, never fake animation
- **$0 MVP spend** — Gemini free tier + Tavily free tier; every LLM call flows through one swappable gateway
- **Modular monolith** — FastAPI service with strict module boundaries; microservices only when pain demands

## Tech stack (summary)

| Layer | Choice |
|---|---|
| Frontend | Next.js · TypeScript · Tailwind · shadcn/ui · React Flow |
| Backend | FastAPI · Python 3.12 · SQLAlchemy 2 · Alembic |
| Data | PostgreSQL 16 + pgvector · Redis · Celery · SSE |
| AI | LLM Gateway → Gemini (primary) · Tavily (search) · Ollama (local dev) |
| Infra | Docker Compose · GitHub Actions · Vercel + Fly.io + Neon |

Full stack rationale and architecture: see [docs/BLUEPRINT.md](docs/BLUEPRINT.md).

## Documentation

| Doc | Purpose |
|---|---|
| [docs/BLUEPRINT.md](docs/BLUEPRINT.md) | Approved system architecture & roadmap |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Vision, taglines, brand identity |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## License

[MIT](LICENSE)
