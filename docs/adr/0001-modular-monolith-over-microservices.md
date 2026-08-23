# ADR 0001 — Modular Monolith over Microservices

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

Nexora's blueprint lists many candidate services (auth, projects, files, orchestrator,
agents, RAG, search, worker). The team is one solo student developer; the product must
ship an MVP quickly while remaining professionally structured.

## Decision

Build a **FastAPI modular monolith** with strict internal packages (`auth`, `projects`,
`files`, `rag`, `agents`, `orchestrator`, `llm`, `security`) deployed as **two
processes**: `api` (HTTP + SSE) and `worker` (Celery). Module boundaries are enforced by
import discipline so future extraction is mechanical. Extraction order when pain
appears: RAG ingestion worker (already separate via Celery) → orchestrator/agent runner.

## Consequences

+ Single deployable to reason about; transactions span modules; fast local dev;
  honest resume claim: "designed module boundaries enabling extraction"
− Requires discipline to prevent cross-module shortcut imports (mitigated by lint rules)
− Eventual scaling of one hot module means extracting it later (deferred deliberately)
