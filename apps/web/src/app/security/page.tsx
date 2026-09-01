"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { Shield, AlertTriangle, CheckCircle } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getToken } from "@/lib/api";

type SecurityHealth = {
  overall_score: number;
  overall_status: string;
  blocked_24h: number;
  total_7d: number;
  dimensions: Record<string, { score: number; status: string; events_24h: number }>;
};

export default function SecurityPage() {
  const router = useRouter();
  const [health, setHealth] = React.useState<SecurityHealth | null>(null);
  const [events, setEvents] = React.useState<unknown[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    Promise.all([
      apiFetch<SecurityHealth>("/security/health").catch((e) => { throw e; }),
      apiFetch<unknown[]>("/security/events?limit=20").catch(() => [] as unknown[]),
    ]).then(([h, ev]) => { setHealth(h); setEvents(ev as unknown[]); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading security…</div></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Shield className="h-5 w-5" /> Security Center</h1>
          <p className="text-sm text-muted-foreground">Injection blocks, audit trail, and 4-dimension health — same pipeline the orchestrator enforces per request.</p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        {health && (
          <>
            <section className="grid gap-3 sm:grid-cols-4">
              <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Overall</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{health.overall_score}<span className="text-sm font-normal text-muted-foreground">/100</span></p><p className={`text-xs ${health.overall_status === "healthy" ? "text-emerald-500" : "text-amber-500"}`}>{health.overall_status}</p></CardContent></Card>
              <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Blocked (24h)</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{health.blocked_24h}</p><p className="text-xs text-muted-foreground">injection / SSRF / authz blocks</p></CardContent></Card>
              <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Total events (7d)</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{health.total_7d}</p></CardContent></Card>
              <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Dimensions</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">{Object.entries(health.dimensions).map(([k, v]) => <div key={k} className="flex justify-between"><span className="text-muted-foreground">{k}</span><span className={v.status === "healthy" ? "text-emerald-500" : "text-amber-500"}>{v.score}</span></div>)}</CardContent></Card>
            </section>
            {health.overall_score >= 90 ? <p className="flex items-center gap-1 text-xs text-emerald-600"><CheckCircle className="h-3 w-3" /> System healthy — guards active on every tool call.</p> : <p className="flex items-center gap-1 text-xs text-amber-600"><AlertTriangle className="h-3 w-3" /> Review events below.</p>}
          </>
        )}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Recent security events</CardTitle></CardHeader>
          <CardContent>
            {(events as unknown[]).length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">No events yet — injection detector, SSRF guard, and permission gate are running. Try a chat that would trigger a block to see it here.</p> : <pre className="max-h-[480px] overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(events.slice(0, 10), null, 2)}</pre>}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
