# Nexora — Permanent Deployment

This repo is ready for one-click permanent deployment.

## Live links (after you deploy)

- **Frontend (Vercel):** `https://nexora.vercel.app` (or your Vercel URL)
  - `https://nexora.vercel.app/workflows` — list
  - `https://nexora.vercel.app/workflows/builder` — React Flow builder
  - `https://nexora.vercel.app/login` — auth
- **Backend API (Render):** `https://nexora-core-api.onrender.com`
  - Health: `https://nexora-core-api.onrender.com/health`
  - Docs: `https://nexora-core-api.onrender.com/docs`
  - OpenAPI: `https://nexora-core-api.onrender.com/openapi.json`
- **GitHub:** `https://github.com/riddhishah007/nexora`

Until you deploy, local links are:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

## Option A — Vercel (frontend) + Render Free (backend) — **$0 Free Permanent (Current — Path A)**

> **You chose Path A.** Frontend on `Vercel Hobby` `$0`. Backend on **single `Free` web service** (`render.yaml:8` `plan: free`, merged `core-api+worker` via `services/core-api/app/main.py:34` lifespan) + `Supabase` pgvector + `Upstash` Redis. No `Render Postgres/Redis` (Free expires `30 days`/`sleep`), no separate `worker` (`Free` has no `type: worker` — `Starter $7/mo` min). Stays within `750` hrs/mo (`1` service `~720 hrs`).

### 1. Create Supabase + Upstash first (required for Free tier)

1. **Supabase** (free): https://supabase.com → `New project` → region `ap-south-1` → `SQL Editor` → paste `supabase/enable_pgvector.sql:3` (`CREATE EXTENSION IF NOT EXISTS vector;`) → `Run` → `Project Settings → Database → Connection string → URI` (Transaction pooler, remove `?pgbouncer=true` for `asyncpg`). Save as `DATABASE_URL`.
2. **Upstash** (free): https://upstash.com → `Create Redis` → region `ap-south-1` → copy `Redis URL` (`redis://` or `rediss://`). Save as `REDIS_URL`.

### 2. Render — single Free web service (Blueprint)

1. Go to https://dashboard.render.com/blueprints → **New Blueprint Instance**
2. Connect repo `riddhishah007/nexora`
3. Render will read `render.yaml` at root and create **1 service**:
   - `nexora-core-api` (`plan: free`, `dockerContext: .`, `dockerfilePath: ./services/core-api/Dockerfile`, `healthCheckPath: /health`) — Docker image already runs `alembic upgrade head && uvicorn` (`services/core-api/Dockerfile:12`) and merged worker in lifespan
4. In Render dashboard `Environment → Secrets` for `nexora-core-api`, set:
    - `DATABASE_URL` = your Supabase URI (`sync: false`)
    - `REDIS_URL` = your Upstash URL (`sync: false`, `rediss://` ok via `redis.from_url`)
    - `GROQ_API_KEY` (https://console.groq.com) or `GEMINI_API_KEY` (for `text-embedding-004` `app/config.py:42`)
    - `SEARCH_API_KEY` (Tavily)
    - `JWT_SECRET`/`REFRESH_TOKEN_SECRET` are `generateValue: true` (or set your own `openssl rand -hex 32`)
5. Set `CORS_ALLOWED_ORIGINS` to your Vercel URL, e.g. `https://nexora.vercel.app` (update after Vercel step)
6. `Manual Deploy → Deploy` → wait for `alembic upgrade head` (`pgvector` + `jobs` + `security_events` + chunks `VECTOR(768)`) → `https://nexora-core-api-xxxx.onrender.com/health` → `200` + `X-Request-ID`
7. Copy the **core-api URL** (e.g. `https://nexora-core-api-xxxx.onrender.com`) — `Free` service sleeps after `15 min` idle (`~60s` cold start on next request; worker pauses while asleep — keep-alive ping every `10 min` optional but consumes hours).

### 2. Vercel (frontend)

1. Go to https://vercel.com/new → Import `riddhishah007/nexora`
2. **Root Directory:** `apps/web`
3. **Environment Variables:**
   - `NEXT_PUBLIC_API_URL` = `https://<your-core-api>.onrender.com/api/v1`
4. Deploy — Vercel will run `npm ci && npm run build` (see `apps/web/package.json`)

### 3. Wire them

- In Vercel, ensure `NEXT_PUBLIC_API_URL` points to your Render core-api URL
- In Render, ensure `CORS_ALLOWED_ORIGINS` includes your Vercel URL
- Redeploy both

## Option B — Fly.io + Supabase + Upstash — **Paid permanent (~$4/mo, always-on)**

> Not your current path (you chose **Option A `$0`**). Keep for later if you want always-on without sleep/expiry. Configs remain in repo for upgrade:
- `services/core-api/fly.toml` (core-api, `bom` region)
- `fly.worker.toml` (worker, root context, `services/worker/Dockerfile`)
- `supabase/enable_pgvector.sql`

### 1. Supabase Postgres (free, has pgvector)

1. Go to https://supabase.com → **New project** (free) → pick region `ap-south-1` (Mumbai) or `ap-southeast-1`
2. **SQL Editor** → paste `supabase/enable_pgvector.sql`:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   SELECT * FROM pg_extension WHERE extname='vector';
   ```
   → **Run** (should show `vector`)
3. **Project Settings → Database** → copy **Connection string → URI** (use `postgresql://...` with `?pgbouncer=true` removed for direct, or keep `pooler` for serverless)
4. This is your `DATABASE_URL` (e.g. `postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres`)

### 2. Upstash Redis (free)

1. Go to https://upstash.com → **Create Redis** (free) → region `ap-south-1` or `us-east-1`
2. Copy **Redis URL** (e.g. `redis://default:<password>@<host>:6379`)
3. This is your `REDIS_URL`

### 3. Fly.io — Core API + Worker (~$4/mo pay-as-you-go, 2026: no free tier — `fly.io/docs/about/cost-management`)

Install `flyctl` if you don’t have it:
```bash
# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
# or scoop: scoop install flyctl
fly auth login
```

**Core API:**
```bash
# from repo root
fly launch --config services/core-api/fly.toml --no-deploy
# fly will ask to create app `nexora-core-api` → yes, region `bom` → no postgres/redis (we use Supabase/Upstash)
fly secrets set DATABASE_URL="postgresql://..." REDIS_URL="redis://..." GROQ_API_KEY="gsk_..." GEMINI_API_KEY="..." SEARCH_API_KEY="tvly-..." JWT_SECRET="$(openssl rand -hex 32)" REFRESH_TOKEN_SECRET="$(openssl rand -hex 32)" CORS_ALLOWED_ORIGINS="https://nexora.vercel.app" LLM_PROVIDER="groq" --app nexora-core-api
fly deploy --config services/core-api/fly.toml
fly status --app nexora-core-api  # wait for health
fly logs --app nexora-core-api    # should show alembic 0008 + uvicorn
```

**Worker:**
```bash
fly launch --config fly.worker.toml --no-deploy
# app `nexora-worker`, same region
fly secrets set DATABASE_URL="postgresql://..." REDIS_URL="redis://..." GROQ_API_KEY="gsk_..." GEMINI_API_KEY="..." --app nexora-worker
fly deploy --config fly.worker.toml
fly logs --app nexora-worker  # should show [worker] subscribed to nexora:queue:default
```

Copy the **core-api URL**: `https://nexora-core-api.fly.dev` (or `fly status` shows `Hostname`)

### 4. Vercel — Frontend (free)

Same as Option A step 2, but set:
- `NEXT_PUBLIC_API_URL` = `https://nexora-core-api.fly.dev/api/v1` (your Fly URL, not Render)

### Why this is permanent (but not $0)

- **Supabase:** 500 MB DB, 50k MAU, `pgvector` included — free forever
- **Upstash:** 10k commands/day, 1 GB — free
- **Fly.io:** `shared-cpu-1x 256MB ~$1.94/mo` each (`core-api`+`worker` ~$4/mo) + storage/bandwidth — pay-as-you-go from first second (no free tier 2026)
- **Vercel:** Hobby free — `nexora.vercel.app`

## Option C — Instant temporary (ngrok)

```bash
ngrok http 3000 --host-header=localhost:3000  # frontend
ngrok http 8000 --host-header=localhost:8000  # backend
```

Gives you `https://<random>.ngrok.io` for 2 hours, no deploy needed.

## Environment variables checklist (Phase 34 Path A)

| Var | Where | Required | Notes |
|-----|-------|----------|-------|
| `DATABASE_URL` | Render `nexora-core-api` (`sync: false`) | yes | Supabase URI (`supabase/enable_pgvector.sql:3` `vector` already enabled) — not Render DB |
| `REDIS_URL` | Render `nexora-core-api` (`sync: false`) | yes | Upstash URL (`redis://` or `rediss://`) — not Render Key Value |
| `JWT_SECRET` | Render (`generateValue: true`) | yes | |
| `REFRESH_TOKEN_SECRET` | Render (`generateValue: true`) | yes | |
| `GROQ_API_KEY` or `GEMINI_API_KEY` | Render (`sync: false`) | one required | `GROQ` for chat, `GEMINI` for `text-embedding-004` `app/config.py:42` |
| `SEARCH_API_KEY` | Render (`sync: false`) | for real search, else mocks | Tavily |
| `NEXT_PUBLIC_API_URL` | Vercel | yes | `https://<render>.onrender.com/api/v1` |
| `CORS_ALLOWED_ORIGINS` | Render `nexora-core-api` | yes | `https://<vercel>.vercel.app` |
| `ENVIRONMENT` | Render | `production` | disables local defaults `app/config.py:15` |
| `LLM_PROVIDER` | Render | `groq` | `groq` recommended for Free tier latency |

## Verify after deploy (Phase 34 smoke — same as `scripts/smoke.py:1`)

```bash
curl https://<core-api>/health          # {"status":"ok"} + X-Request-ID services/core-api/app/middleware/request_id.py:1
curl https://<core-api>/metrics         # nexora_http_requests_total services/core-api/app/routers/metrics.py:1
curl https://<core-api>/api/v1/agents   # 200 public registry
curl -X POST https://<core-api>/api/v1/agents/run -H "Content-Type: application/json" -d '{"agent_id":"search-agent","input":{"query":"test"}}' # 401 without token

# Full smoke (7 checks)
python scripts/smoke.py --base https://<core-api>.onrender.com
# → GET /health + X-Request-ID OK, /metrics OK, / OK, /agents 200 + /agents/run 401, /rag/search 401, auth register→login→GET /agents OK, RAG eval offline 3 cases OK → PASS scripts/smoke.py:166

# RAG ingest (merged worker) end-to-end
# After smoke auth: upload PDF → POST /api/v1/documents → job queued → merged worker (lifespan) drains queue → GET /rag/search → citations
```

Frontend will then be live at your Vercel URL with the Workflow Builder at `/workflows/builder`. Note `Free` tier sleeps after `15 min` idle — first hit after idle `~60s` cold start before `X-Request-ID` appears.
