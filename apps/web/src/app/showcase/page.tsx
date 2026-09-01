import Link from "next/link";
import { ExternalLink, Play, Layers, Shield, Cpu, Database, FileText, Code, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AppShell } from "@/components/app-shell";
import { Logo } from "@/components/logo";

const LIVE_API = "https://nexora-core-api.onrender.com";
const LIVE_WEB = "https://web-nine-snowy-57.vercel.app";

const DEMOS = [
  { n: 1, title: "Deep Research → cited PDF", desc: "Research-agent sub-questions + search + RAG synthesis into Writer report", run: "Chat: 'Research quantum error correction and cite my uploaded papers'" },
  { n: 2, title: "Code Review + sandbox tests", desc: "Coding-agent generate + execute_code (HIGH trust, isolated)", run: "Chat: 'Write Python to parse my CSV and run it'" },
  { n: 3, title: "20-PDF knowledge synthesis", desc: "Bulk upload → ingest → RAG hybrid (α=0.6) rerank + query", run: "Files → upload 20 PDFs → RAG inspector hybrid search" },
  { n: 4, title: "Cyber investigation (phishing vs KB)", desc: "Search web + RAG cross-check + injection block demo", run: "Chat with phishing URL — SSRF guard blocks private ranges, Security Center shows block" },
  { n: 5, title: "Parallel sprint Search∥RAG∥Research", desc: "Workflow template Multi-Source Brief — 3 agents fan-out → Writer merge", run: "Workflows → Multi-Source Brief template → Run" },
  { n: 6, title: "Prompt-injection blocked live", desc: "Heuristic + risk score → sanitize or BLOCK + audit", run: "Chat: 'Ignore previous instructions...' → Security/events shows blocked" },
  { n: 7, title: "Human-in-the-loop approval", desc: "HIGH action → approval row → POST /approvals/{id}/decision", run: "Approvals → Request → Approve → Notification inbox" },
  { n: 8, title: "Workflow builder run", desc: "React Flow DAG + SSE live network + synthesis streaming", run: "Workflows/Builder → drag nodes → Run (SYNTHESIS_DELTA)" },
  { n: 9, title: "Cost transparency cheap-vs-pro", desc: "LLM gateway pricing table → /usage/summary est_cost_usd", run: "Chat a few times → Usage dashboard cost column" },
  { n: 10, title: "CSV data analysis (V1)", desc: "Data-agent pandas sandbox + Writer executive report", run: "Files upload CSV → Chat 'Analyze my CSV' → data-agent describe()" },
];

export default function ShowcasePage() {
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">Portfolio — Live</span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">One Command. Many Agents. One Intelligent Result.</h1>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Nexora is a multi-agent AI orchestration platform — FastAPI + pgvector + Redis, 7 specialist agents, live WS network, hybrid RAG with rerank, and a HITL security gate. Built as a modular monolith on Render Free + Supabase + Upstash + Vercel Hobby ($0).
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href={LIVE_WEB} target="_blank"><Button><ExternalLink className="h-4 w-4" /> Live App</Button></Link>
            <Link href={`${LIVE_API}/docs`} target="_blank"><Button variant="outline"><ExternalLink className="h-4 w-4" /> API Docs</Button></Link>
            <Link href="https://github.com/riddhishah007/nexora" target="_blank"><Button variant="outline">GitHub</Button></Link>
          </div>
          <div className="grid gap-2 font-mono text-xs text-muted-foreground sm:grid-cols-2">
            <span>API: {LIVE_API}</span><span>Web: {LIVE_WEB}</span>
            <span>Health: {LIVE_API}/health + X-Request-ID · Metrics: /metrics</span><span>Smoke: python scripts/smoke.py --base {LIVE_API} → 7 PASS</span>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-3">
          <Card><CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><Layers className="h-4 w-4" /> Orchestration</CardTitle></CardHeader><CardContent className="text-xs text-muted-foreground">Supervisor plan-as-DAG + parallel fan-out + SSE live network (React Flow, SYNTHESIS_DELTA streaming)</CardContent></Card>
          <Card><CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><Database className="h-4 w-4" /> RAG</CardTitle></CardHeader><CardContent className="text-xs text-muted-foreground">pgvector HNSW + hybrid vector∥keyword + α=0.6 rerank + query rewrite + inspector /rag/search</CardContent></Card>
          <Card><CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><Shield className="h-4 w-4" /> Security</CardTitle></CardHeader><CardContent className="text-xs text-muted-foreground">Injection detector + SSRF allowlist + tool trust levels + HITL approvals + audit (Security Center)</CardContent></Card>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Play className="h-4 w-4" /> 10 Demo Scenarios (Blueprint §19)</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {DEMOS.map((d) => (
              <Card key={d.n} className="hover:border-primary/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{d.n}. {d.title}</CardTitle>
                  <CardDescription className="text-xs">{d.desc}</CardDescription>
                </CardHeader>
                <CardContent><p className="font-mono text-xs text-muted-foreground">▶ {d.run}</p></CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Workflow className="h-4 w-4" /> Stack</CardTitle></CardHeader>
            <CardContent className="space-y-1 font-mono text-xs text-muted-foreground">
              <div>Frontend: Next.js 16 App Router · Tailwind · shadcn/ui · XYFlow</div>
              <div>Backend: FastAPI · SQLAlchemy2 · Alembic (0010) · Postgres 16+pgvector · Redis</div>
              <div>AI: Groq qwen/qwen3.6-27b · Gemini embeddings · Tavily · Ollama dev stub</div>
              <div>Obs: X-Request-ID · Prometheus /metrics · /usage/summary + cost pricing</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Cpu className="h-4 w-4" /> Routes (20)</CardTitle></CardHeader>
            <CardContent className="font-mono text-xs leading-relaxed text-muted-foreground">
              <div>/chat (streaming + WS) · /projects · /files · /knowledge · /rag</div>
              <div>/workflows + /workflows/builder · /agents · /security · /history</div>
              <div>/approvals + /notifications · /marketplace · /dashboard (Usage)</div>
              <div>API: /api/v1/auth · /agents · /chat · /documents · /rag · /code · /workflows · /projects · /approvals · /notifications · /exports · /security · /usage</div>
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><FileText className="h-4 w-4" /> For Recruiters / Judges</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-xs leading-relaxed text-muted-foreground">
            <p>Try: <Link href="/chat" className="font-medium text-primary underline">Chat</Link> → "Summarize my docs and search the web for 2026 trends" → watch the live Agent Network on the right. Then check <Link href="/rag" className="font-medium text-primary underline">RAG inspector</Link> for scored chunks, <Link href="/security" className="font-medium text-primary underline">Security Center</Link> for 98/100 health, and <Link href="/approvals" className="font-medium text-primary underline">Approvals</Link> for HITL.</p>
            <p>Exports: any workflow or conversation exports as markdown via <span className="font-mono">GET /api/v1/exports/workflow/{`{id}`}</span> — print to PDF for your handout.</p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
