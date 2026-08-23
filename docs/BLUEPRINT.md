# NEXORA — Project Blueprint V1 (Approved)

> **One Command. Many Agents. One Intelligent Result.**
> Approved 2026-08-23. This document is the development specification.

---

## 1. Brand

**Direction:** Developer AI core, restrained futurism. Audience: developers, recruiters,
hackathon judges — precision signals competence better than glow.

- **Meaning:** *Nexus* + *Aura* — a hub where capabilities connect
- **Logo:** hexagonal node, radiating connections converging inward
- **Palette:** base `#0A0D14` · surface `#11151F` · indigo→violet `#6366F1→#8B5CF6`
  (orchestrator) · cyan `#22D3EE` (active agents) · emerald · amber · red (security)
- **Typography:** Geist/Inter (UI) + JetBrains Mono (code, agent IDs)
- **Motion:** springs 150–300ms; motion communicates state only; reduced-motion honored

## 2. Taglines

1. **One Command. Many Agents. One Intelligent Result.** ⭐ primary
2. Your AI Team, On Command (secondary)
3. Orchestrate Intelligence · 4. Many Minds. One Mission. · 5. Where Agents Become Answers
6. Think Once. Execute Everywhere. · 7. The Command Center for Autonomous AI
8. From Prompt to Production-Grade Result · 9. One Intent. Infinite Capability.
10. Delegate Everything. Achieve More. · 11. Intelligence, Orchestrated.
12. Ask Big. We Deploy the Team. · 13. Beyond Chatbots. Into Systems.
14. Every Task Has a Specialist. · 15. Plan. Delegate. Deliver.
16. AI That Works Like a Team. · 17. Turn Questions Into Operations.
18. The Brain Behind Your Bots. · 19. Command Complexity. · 20. Not a Chat. A Workforce.

## 3. Product vision

See [PRODUCT.md](PRODUCT.md).

## 4. Feature tiers

**MVP:** Auth → Dashboard → Projects → AI Workspace → Orchestrator v1 → Agents:
Coding, Search, PDF/RAG, Writer-lite → Tool system → pgvector RAG with citations →
live agent network via SSE → fixed workflow templates → JWT + rate limits + input
guards → Docker Compose → usage tracking → premium dark UI.

**V1:** Research, Security, Data Analysis, Writer-full agents · workflow builder ·
parallel fan-out · human approvals · cost dashboard · marketplace UI · hybrid search +
rerank · Security Center · notifications · exports.

**V2:** Custom agents · developer API + keys · webhooks · Ollama in routing · agent
versioning + A/B · prompt management · advanced memory · teams.

## 5. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14+ App Router · TypeScript · Tailwind CSS · shadcn/ui · Motion · React Flow |
| State | TanStack Query + Zustand |
| Backend | FastAPI · Python 3.12 · SQLAlchemy 2.0 · Alembic · Pydantic v2 |
| Data | PostgreSQL 16 + pgvector · Redis 7 (cache + broker + pub/sub) · Celery |
| Storage | interface → local disk (dev) → Cloudflare R2 / Supabase (prod) |
| Auth | self-built JWT access(15m)+rotating refresh(7d), bcrypt, RBAC |
| AI | LLM Gateway → Gemini primary · Tavily search · Ollama dev · OpenAI fallback |
| Observability | structlog JSON · Prometheus /metrics · own usage dashboard |
| CI/CD | GitHub Actions (lint→types→unit→integration→security scan→build→deploy) |
| Hosting | Vercel (web) · Fly.io/Render (api+worker) · Neon (Postgres+pgvector) · Upstash (Redis) |

## 6. API-key strategy ($0 MVP)

Frontend never holds keys. All traffic through one LLM Gateway module
(router · prompt registry · token/cost accounting · Redis cache · provider adapters).

| Key | Purpose | Cost |
|---|---|---|
| `GEMINI_API_KEY` | ALL LLM calls + embeddings | free tier |
| `TAVILY_API_KEY` | Search Agent web results | free 1k req/mo |

Secrets live only server-side in `.env`: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`,
`JWT_REFRESH_SECRET`, storage creds. Boot fails fast on missing config (Pydantic Settings).

## 7. Agent architecture

Supervisor + plan-as-state-machine + event-driven execution (see ADR 0004).
Flow: goal → Planner (structured DAG referencing registry agent IDs) → persisted
workflow/workflow_steps → Execution Engine runs dependency-satisfied steps (parallel
fan-out supported) → each step = AgentRun with schema-validated output (repair-retry ×2)
→ events on every transition → Synthesizer merges → answer + citations.

**Roster:** MVP = Orchestrator, Coding, Search, PDF/Document, Knowledge(RAG),
Writer-lite · V1 = Research, Security, Data Analysis, Writer-full.

**Agent Registry:** DB-seeded from YAML manifests; entries carry id, name, version,
capabilities, tasks, tools, permissions, model class, status, cost profile, latency,
success rate. Orchestrator never hard-codes agents.

**Tool system:** async functions + Pydantic schemas + trust level + timeout +
permissions checked per calling agent (deny by default). Every call logged to
`tool_calls`.

**Permission matrix (summary):**

| Agent | read files | write | run code | web fetch | KB query | external POST |
|---|---|---|---|---|---|---|
| Coding | sandbox | sandbox | sandbox HIGH | ✗ | ✓ | ✗ |
| Search | ✗ | ✗ | ✗ | allowlist | ✗ | ✗ |
| Research | KB | ✗ | ✗ | ✓ | ✓ | ✗ |
| PDF/RAG | own docs | ✗ | ✗ | ✗ | ✓ | ✗ |
| Writer | KB | ✗ | ✗ | ✗ | ✓ | ✗ |
| Security | read-only | ✗ | ✗ | ✓ | ✓ | ✗ |

Trust levels: LOW (calculator, summarize) · MEDIUM (search, file read, KB query) ·
HIGH (code exec, external side effects, deletion → human approval required).

## 8. RAG

pgvector (ADR 0002). Pipeline: upload → validate (type/magic bytes ≤20MB) → parse
(PyMuPDF/docx/csv) → clean → chunk 800–1200 tokens, 10–15% overlap on headings →
metadata(project, kb, doc, page, section) → batch embeddings (text-embedding-004) →
upsert chunks(vector 768 + tsvector) → index ✓.
Retrieval: rewrite → hybrid vector top-20 ∥ FTS top-20 → RRF fusion → rerank top-8 →
context assembly ≤ ~6k tokens → cited answer bound to chunk IDs. Tenant filter enforced
in repository layer.

## 9. Memory

Short-term = messages · Long-term = explicit pins + confirmed extractions (`memories`)
· Knowledge = chunks. Never silent save-all; per-item view/delete/export.

## 10. Database (PostgreSQL 16)

users · organizations · memberships · sessions · projects · conversations · messages ·
agents · agent_versions · agent_runs · workflows · workflow_steps · knowledge_bases ·
documents · chunks(vector) · tools · tool_calls · api_usage · audit_logs · files ·
api_keys · webhooks + deliveries · notifications · approvals · share_links · prompts.
Tenant-scoped indexes `(project_id, created_at)`; HNSW + GIN on chunks; isolation
enforced in repositories.

## 11. Services & events

Modular monolith (ADR 0001): FastAPI `api` process + Celery `worker` process.
Queues: ingest / agents / exports — retries ×3 backoff, dead-letter table, idempotency
keys. Live events: Redis Pub/Sub `run:{id}` → SSE endpoint → browser (ADR 0005).
Events: TASK_CREATED, AGENT_SELECTED, AGENT_STARTED, TOOL_STARTED, TOOL_COMPLETED,
AGENT_COMPLETED, AGENT_FAILED, STEP_SKIPPED, APPROVAL_REQUIRED, WORKFLOW_COMPLETED,
FINAL_RESPONSE_READY. Payloads contain high-level labels only — never raw reasoning.

## 12. Security

JWT rotation + reuse detection · bcrypt · RBAC · Pydantic validation everywhere ·
slowapi rate limits · CORS allowlist · secure headers. Files: extension allowlist,
magic-byte sniff, UUID names, ACL checks, ClamAV hook optional.
AI security layers: injection detector (heuristics + risk score → sanitize or BLOCK +
audit) → least-privilege agent → tool gate (allowlist/trust/approval) → output schema
validation (repair-retry) → PII/secret scrubber. SSRF guards on fetch tools (resolve
DNS, block private ranges, domain allowlist). Code execution: ephemeral Docker sandbox
— network off, read-only rootfs, CPU/mem caps, timeouts; gVisor/Firecracker documented
as production upgrade. HITL approval flow pauses/resumes workflows for HIGH actions.

## 13. Frontend

Dark-first premium; layered near-black surfaces, 1px borders rgba(255,255,255,.08);
glass ≤2 surfaces/screen. Pages: landing · login/register · dashboard · workspace
(Command Center) · agents · marketplace · projects · knowledge · files · research ·
code · workflows (+builder) · history · usage · security · settings · admin ·
developers (V2) · showcase.
Command Center: left chat rail · center answer canvas (markdown, citations, export) ·
right live Agent Network (React Flow, real SSE states ●✓!◌) + activity timeline tabs ·
bottom status strip (tokens · cost · latency · model).
Workflow builder: XYFlow canvas, node palette (Agent/Tool/Condition/Approval/Input/
Output), inspector panel, template gallery, run overlay driven by real events.
Command palette Ctrl+K across everything. Full responsive + accessibility
(keyboard, ARIA, focus states, reduced motion).

## 14. API (/api/v1)

REST · Pydantic schemas · cursor pagination · RFC-7807-style errors · OpenAPI docs auto.
auth/* · projects · chat/{id}/messages (SSE stream) · agents(+run) · files/upload ·
knowledge-bases(+query) · workflows(+execute) · tasks/{id} · runs/{id}/events (SSE) ·
approvals/{id}/decision · usage/summary · admin/security-events · developers/* (V2).

## 15. Docker / CI/CD / Cloud

Compose dev services: web · api · worker · postgres(pgvector) · redis · minio · ollama
profiles; healthchecks; named volumes; prod override (gunicorn, nginx TLS, restarts).
CI: ruff+eslint → mypy+tsc → pytest+vitest → integration (compose pg/redis) → pip-audit
+ trivy → docker build. CD: GHCR images → Fly/Render hooks; Vercel auto for web.
Conventional commits; protected main.
Hosting ≈ $0: Vercel + Fly.io + Neon + Upstash + R2 free tiers. Kubernetes rejected.

## 16. Testing & observability

Unit (routing/chunking/guards/permissions) · integration (httpx + containers, tenant
isolation tests) · agent tests (gateway mocked w/ fixtures) · RAG eval golden set
(hit@5 ≥ 0.8 gate) · security corpus (50 injections blocked, SSRF probes, authz sweep)
· Playwright E2E smoke.
Observability: structlog JSON with request_id/run_id · Prometheus histograms
(latency per route/agent/tool, token/cost counters, queue depth) · usage dashboard from
own tables · Grafana optional profile · OTel deferred to V2.

## 17. Repository structure

```
nexora/
├── apps/web/          Next.js + TS + Tailwind + shadcn/ui + XYFlow
├── server/            FastAPI modular monolith
│   └── app/
│       ├── api/v1/    routers (thin)
│       ├── core/      config, security, logging, deps
│       ├── db/        models, repositories, alembic/
│       ├── llm/       GATEWAY: router, prompts/, providers/
│       ├── orchestrator/  planner, engine, synthesizer, events
│       ├── agents/    base.py, registry.py, coding/ search/ pdf/ rag_agent/ writer/
│       ├── tools/     registry.py + implementations
│       ├── rag/       parsers, chunker, embedder, retriever, reranker
│       ├── security/  injection guard, validators, scrubber, ssrf, approval
│       ├── workers/   celery app + tasks
│       └── events/    redis publisher, sse manager
├── infrastructure/    docker/, monitoring/, nginx/
├── docs/              this blueprint, PRODUCT.md, adr/
└── .github/workflows/ ci.yml, deploy.yml
```

## 18. Roadmap

Ph0 product definition/repo ✓ → Ph1 monorepo skeleton+lint → Ph2-3 design system+
landing → Ph4-6 backend+auth+database → Ph7 LLM Gateway → Ph8-10 first agent+
orchestrator+tools+SSE → Ph11-12 PDF+RAG → Ph13-14 Search+Research → Ph15-16 multi-
agent workflows+live network → Ph17-18 workers/queues → Ph19-20 security+center →
Ph21 observability → Ph22-24 prod compose+tests+CI/CD → Ph25 cloud deploy → Ph26-27
polish+portfolio/demo mode. Realistic solo pace ~3-5 months part-time.

## 19. Demo scenarios

1 Deep Research→cited PDF · 2 Code Review+sandbox tests · 3 20-PDF knowledge synthesis ·
4 Cyber investigation (phishing vs my KB) · 5 Parallel sprint Search∥RAG∥Security ·
6 Prompt-injection blocked live · 7 Human-in-the-loop approval · 8 Workflow builder run
· 9 Cost transparency cheap-vs-pro routing · 10 CSV data analysis (V1).

## 20. Success criteria

Multi-agent orchestration · routing · tool calls · RAG+citations · parallel agents ·
workers · Postgres/Redis/Docker · authn/authz · AI security controls · API docs ·
testing · CI/CD · cloud deploy · premium UI (landing/dashboard/workspace/network/
builder/realtime/animations/a11y/themes) · products (projects/KBs/workflows/marketplace
architecture/developer API architecture/usage/security center) · portfolio (GitHub,
live demo, video, diagrams, docs, write-up).
