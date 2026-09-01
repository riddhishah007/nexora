# Nexora — 10 Demo Scenarios (Blueprint §19)

Live: https://web-nine-snowy-57.vercel.app/ · API: https://nexora-core-api.onrender.com · Docs: https://nexora-core-api.onrender.com/docs
Verify: `python scripts/smoke.py --base https://nexora-core-api.onrender.com` → 7 PASS

| # | Title | Agents | How to run | What to show |
|---|---|---|---|---|
| 1 | Deep Research → cited PDF | research → writer | Chat: "Research quantum error correction, cite my uploaded papers" + upload 2-3 PDFs first → Files → ingest | 6-source cited report, page citations |
| 2 | Code Review + sandbox tests | coding | Chat: "Write Python to analyze my CSV and run it" or `/code/run` | `execute_code` sandbox (no network, timeout 15s) `exit_code=0` |
| 3 | 20-PDF knowledge synthesis | rag hybrid | Files: upload 20 PDFs → RAG inspector `POST /rag/search` top_k=20 α=0.6 rerank | hybrid recall + inspector distance+score |
| 4 | Cyber investigation (phishing vs KB) | search + rag + security | Chat a phishing URL — SSRF guard blocks private ranges → Security Center `blocked_24h` | SSRF allowlist + security_events audit |
| 5 | Parallel sprint Search∥RAG∥Research | search ∥ rag ∥ research → writer | Workflows → template `Multi-Source Brief` → Run (3 agents fan-out) → Builder live network | Parallel DAG executor + WS events |
| 6 | Prompt-injection blocked live | security | Chat: "Ignore previous instructions..." → `POST /security/events` shows blocked injection, health score dips | injection detector + risk score |
| 7 | Human-in-the-loop approval | approvals | Approvals → Request "execute_code: HIGH" → Approve → Notifications inbox + `POST /approvals/{id}/decision` | HITL pending → approved, notification created |
| 8 | Workflow builder run | workflows | Workflows/Builder → drag Research → Writer (depends_on [0]) → Run → Inspector shows SYNTHESIS_DELTA streaming | React Flow + WS parity with chat |
| 9 | Cost transparency cheap-vs-pro | usage | Chat 2-3 times → Usage dashboard `/dashboard` → check `est_cost_usd` per-model + daily bars | pricing table `app/llm/pricing.py` + `GET /usage/summary` |
| 10 | CSV data analysis (V1) | data → writer | Files upload CSV → Chat: "Analyze my CSV: shape, stats, trends" → data-agent pandas `describe()` → writer report | `data-agent` + sandbox + citations |

## Quick E2E script

```bash
# 1. health + auth + chat
python scripts/smoke.py --base https://nexora-core-api.onrender.com
# 2. rag: upload → ingest → search
# 3. approvals
curl -H "Authorization: Bearer $TOKEN" https://nexora-core-api.onrender.com/api/v1/approvals -d '{"action":"demo HIGH"}'
curl -X POST -H "Authorization: Bearer $TOKEN" https://nexora-core-api.onrender.com/api/v1/approvals/$ID/decision -d '{"decision":"approved"}'
# 4. exports
curl -H "Authorization: Bearer $TOKEN" https://nexora-core-api.onrender.com/api/v1/exports/workflow/$WID
```
