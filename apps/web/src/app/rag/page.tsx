"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Database, FileText, Search, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AppShell } from "@/components/app-shell";
import { apiFetch, getToken } from "@/lib/api";

type RagHit = {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  distance: number;
  score: number | null;
};

type RagSearchResponse = {
  query: string;
  hits: RagHit[];
  count: number;
  alpha: number;
  rerank_enabled: boolean;
};

export default function RagInspectorPage() {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [topK, setTopK] = React.useState(5);
  const [docId, setDocId] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<RagSearchResponse | null>(null);

  React.useEffect(() => {
    if (!getToken()) router.push("/login");
  }, [router]);

  async function onSearch(e?: React.FormEvent) {
    e?.preventDefault();
    const q = query.trim();
    if (!q) {
      setError("Enter a query");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { query: q, top_k: topK };
      const d = docId.trim();
      if (d) body.document_id = d;
      const res = await apiFetch<RagSearchResponse>("/rag/search", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-center gap-3">
        <Link href="/chat">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> Chat
          </Button>
        </Link>
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Database className="h-5 w-5 text-violet-500" /> RAG Inspector
          </h1>
          <p className="text-sm text-muted-foreground">
            Search your ingested chunks with hybrid vector + keyword scoring. Scores surface the Phase 28 rerank.
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Link href="/dashboard">
            <Button variant="outline" size="sm">Usage</Button>
          </Link>
          <Link href="/workflows">
            <Button variant="outline" size="sm">Workflows</Button>
          </Link>
        </div>
      </header>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Search className="h-4 w-4 text-primary" /> Query
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSearch} className="flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="What was mentioned about pgvector or nexora…"
                className="flex-1"
              />
              <Button type="submit" disabled={loading} className="sm:w-auto">
                {loading ? "Searching…" : "Search"}
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <label className="flex items-center gap-1.5 text-muted-foreground">
                <SlidersHorizontal className="h-3.5 w-3.5" /> top_k
                <select
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="rounded-md border border-input bg-background px-2 py-1 text-xs"
                >
                  {[3, 5, 8, 10, 15, 20].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-1 items-center gap-1.5 text-muted-foreground">
                <FileText className="h-3.5 w-3.5" /> document_id (optional)
                <Input
                  value={docId}
                  onChange={(e) => setDocId(e.target.value)}
                  placeholder="filter to one document"
                  className="h-7 flex-1 font-mono text-xs"
                />
              </label>
            </div>
          </form>
          {error && <p className="mt-3 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>}
          {result && (
            <p className="mt-3 font-mono text-xs text-muted-foreground">
              {result.count} hits · α={result.alpha} · rerank={String(result.rerank_enabled)} · query “{result.query}”
            </p>
          )}
        </CardContent>
      </Card>

      {result && result.hits.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No chunks matched. Try a broader query or ingest more documents.
          </CardContent>
        </Card>
      )}

      {result && result.hits.length > 0 && (
        <div className="flex flex-col gap-3">
          {result.hits.map((h, i) => {
            const score = h.score ?? 0;
            const scorePct = Math.round(Math.max(0, Math.min(1, score)) * 100);
            return (
              <Card key={h.chunk_id} className="overflow-hidden">
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">#{i + 1}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      chunk {h.chunk_index} · dist {h.distance.toFixed(4)} · score {score.toFixed(4)}
                    </span>
                    <span className="ml-auto font-mono text-[10px] text-muted-foreground">{h.document_id.slice(0, 8)}</span>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" title={`score ${scorePct}%`}>
                      <div className="h-full bg-violet-500 transition-all" style={{ width: `${scorePct}%` }} />
                    </div>
                    <span className="font-mono text-xs tabular-nums">{scorePct}%</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{h.content}</p>
                  <p className="mt-2 font-mono text-[10px] text-muted-foreground">{h.chunk_id}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {!result && !error && (
        <Card className="border-dashed">
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Enter a query to inspect hybrid retrieval — vector distance + keyword score (Phase 28) are shown per hit.
            <br />
            Tip: try a name or code from an ingested PDF to see keyword hits fix embedding-only misses.
          </CardContent>
        </Card>
      )}
      </div>
    </AppShell>
  );
}
