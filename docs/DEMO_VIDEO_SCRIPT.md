# Demo Video Script — 2 Minutes (for Loom / Portfolio)

> Record at https://web-nine-snowy-57.vercel.app/ with https://nexora-core-api.onrender.com/docs open in second tab. Use a fresh account. Speak slowly — 130 wpm ~ 260 words = 2 min.

## 0:00–0:12 — Hook + Live Proof (12s)
> "One command, many agents, one intelligent result. This is Nexora — live at web-nine-snowy-57.vercel.app on Render Free + Supabase + Vercel. Let's prove it in 2 minutes."

Show: Landing page → click **Live App** → `GET /health` returns `X-Request-ID` in DevTools Network (observability `app/middleware/request_id.py:1`).

## 0:12–0:40 — Chat: One Command, Multi-Agent Plan + Streaming (28s)
> "I type one sentence. The orchestrator plans a DAG, fans out, and streams the answer live."

1. Login → **Chat** `apps/web/src/app/chat/page.tsx:11`.
2. Type: `Research quantum error correction, cite my uploaded paper on surface codes and search the web for 2026 results` → Send.
3. Narrate as it streams: `POST /chat/start` `app/routers/chat.py:97` returns in **2.9s** (plan), then WS `app/routers/realtime.py:44` shows spinners → checks for `search-agent → rag-agent → writer-agent`, plus `SYNTHESIS_DELTA` blinking caret (Phase 25/27).
4. Point to citations `[1][2]` and bottom strip `tokens · cost · latency` (`app/llm/pricing.py:14` + `GET /usage/summary`).

## 0:40–0:55 — RAG Grounding: Hybrid Inspector (15s)
> "Every claim is grounded. This is not chat — it's retrieval with scoring."

1. Click **RAG** `apps/web/src/app/rag/page.tsx:1`.
2. Query `surface code` → show `POST /rag/search` `app/routers/rag.py:215` hits with `distance` + `score = α·(1−distance)+(1−α)·keyword_overlap` (`α=0.6` `services/core-api/app/rag/service.py:28`), document filter, `chunk_id` provenance.
3. Say: "Vector alone misses names/codes — hybrid keyword union + rerank fixes it."

## 0:55–1:10 — Files & Code: Upload + Sandbox (15s)
> "Upload anything — PDF, CSV, XLSX — then ask over it."

1. **Files** `apps/web/src/app/files/page.tsx:1` → Upload a PDF + a CSV → shows `POST /documents` `app/routers/documents.py:76` → `POST /rag/ingest` job queued → merged worker `app/main.py:34` drains it.
2. Quick **Code** demo: Chat `Analyze my CSV: shape, stats, trends` → `data-agent` generates pandas in sandbox `app/routers/code.py:19` (HIGH trust, no network, 15s timeout) → `exit_code=0` output shown.

## 1:10–1:30 — Workflows + Security: Builder + HITL (20s)
> "Repeats become workflows. Dangerous actions need a human."

1. **Workflows** `apps/web/src/app/workflows/page.tsx:1` → **Builder** `Builder.tsx:1` → template **Multi-Source Brief** (search ∥ rag ∥ research → writer) → **Run** → React Flow nodes turn `pending → running → done` via same WS channel. Show LIVE chip.
2. **Security Center** `apps/web/src/app/security/page.tsx:1` → `GET /security/health` `app/routers/security.py:71` shows `overall 98/100`, `blocked_24h`. Trigger injection: Chat `Ignore previous instructions` → blocked + appears in `/security/events`.
3. **Approvals** `apps/web/src/app/approvals/page.tsx:1` → click **Approve** on a pending HIGH action `POST /approvals/{id}/decision` `app/routers/approvals.py:14` → **Notifications** bell increments `app/routers/notifications.py:14`.

## 1:30–1:50 — Marketplace & Usage: Cost Transparency (20s)
> "Templates make experts reusable. Costs are transparent."

1. **Marketplace** `apps/web/src/app/marketplace/page.tsx:1` → 6 templates (Research+RAG, PDF Summary, Code Run, Deep Research Report, CSV Analysis, Multi-Source Brief) → `GET /workflows/templates`.
2. **Usage** `/dashboard` `apps/web/src/app/dashboard/page.tsx:40` → stat cards + daily bars + per-model table with `est_cost_usd` (`GET /usage/summary?days=7`).

## 1:50–2:00 — Close + Links (10s)
> "Modular monolith, 21 routes, 7 agents, pgvector hybrid RAG, HITL, all on $0 infra. Links below."

Show **Showcase** `apps/web/src/app/showcase/page.tsx:14` (`/showcase`): `LIVE_API`, `LIVE_WEB`, `/docs`, GitHub, 10 scenarios table `docs/DEMO_SCENARIOS.md:1`. Say: "Exports are markdown — `GET /exports/workflow/{id}` — print to PDF for your handout. Scripts `smoke.py` `keepalive.py` `demo_portfolio.py` keep it green."

### Pre-flight Checklist (before recording)
- [ ] `python scripts/smoke.py --base https://nexora-core-api.onrender.com` → 7 PASS
- [ ] `python scripts/demo_portfolio.py --base https://nexora-core-api.onrender.com` → DEMO PASS
- [ ] Upload 1 PDF + 1 CSV beforehand so RAG has chunks (or they ingest in 5–10s live)
- [ ] `GET /metrics` shows `nexora_build_info{version="0.2.0",phase="32"}` + `X-Request-ID` header
- [ ] Browser at 125% zoom, dark theme, hide bookmarks bar

### After Recording
- Add Loom link to `README.md:1` hashtag and `apps/web/src/app/showcase/page.tsx:14` hero.
- Add `gh workflow keepalive` badge if desired: `Actions → Keepalive`.

