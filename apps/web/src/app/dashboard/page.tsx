"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Activity, Coins, Gauge, Zap } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch, getToken } from "@/lib/api";
import { cn } from "@/lib/utils";

type ModelUsage = {
  provider: string;
  model: string;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
  est_cost_usd: number;
};

type DailyUsage = { day: string; calls: number; tokens_in: number; tokens_out: number };

type UsageSummary = {
  days: number;
  total_calls: number;
  cached_calls: number;
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
  est_cost_usd: number;
  by_model: ModelUsage[];
  by_day: DailyUsage[];
};

const RANGES = [7, 14, 30] as const;

export default function DashboardPage() {
  const router = useRouter();
  const [days, setDays] = React.useState<number>(7);
  const [summary, setSummary] = React.useState<UsageSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const authed = React.useMemo(() => Boolean(getToken()), []);

  React.useEffect(() => {
    if (!authed) router.push("/login");
  }, [authed, router]);

  React.useEffect(() => {
    if (!authed) return;
    setLoading(true);
    apiFetch<UsageSummary>(`/usage/summary?days=${days}`)
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [authed, days]);

  const cacheRate = summary && summary.total_calls > 0 ? Math.round((summary.cached_calls / summary.total_calls) * 100) : 0;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-center gap-3">
        <Link href="/chat">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> Chat
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Usage</h1>
          <p className="text-sm text-muted-foreground">LLM calls, tokens, and latency across your agents.</p>
        </div>
        <div className="ml-auto flex gap-1 rounded-lg border border-border p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium",
                days === r ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {r}d
            </button>
          ))}
        </div>
      </header>

      {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {!loading && summary && (
        <>
          <section className="grid gap-3 sm:grid-cols-4">
            <StatCard icon={<Activity className="h-4 w-4 text-sky-500" />} label="Requests" value={summary.total_calls.toLocaleString()} sub={`${summary.cached_calls} cached · ${cacheRate}% hit`} />
            <StatCard icon={<Coins className="h-4 w-4 text-violet-500" />} label="Tokens" value={fmt(summary.tokens_in + summary.tokens_out)} sub={`${fmt(summary.tokens_in)} in · ${fmt(summary.tokens_out)} out`} />
            <StatCard icon={<Gauge className="h-4 w-4 text-emerald-500" />} label="Avg latency" value={`${Math.round(summary.avg_latency_ms)} ms`} sub={`last ${summary.days} days`} />
            <StatCard icon={<Zap className="h-4 w-4 text-amber-500" />} label="Est. cost" value={`$${summary.est_cost_usd.toFixed(4)}`} sub="rough list-price estimate" />
          </section>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Requests per day</CardTitle>
            </CardHeader>
            <CardContent>
              {summary.by_day.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No usage in this period yet — run an agent or send a chat.</p>
              ) : (
                <DailyBars byDay={summary.by_day} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">By model</CardTitle>
            </CardHeader>
            <CardContent>
              {summary.by_model.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">Nothing yet.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead className="text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="py-2 font-medium">Model</th>
                      <th className="py-2 font-medium">Provider</th>
                      <th className="py-2 text-right font-medium">Calls</th>
                      <th className="py-2 text-right font-medium">Tokens in</th>
                      <th className="py-2 text-right font-medium">Tokens out</th>
                      <th className="py-2 text-right font-medium">Avg latency</th>
                      <th className="py-2 text-right font-medium">Est. cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.by_model.map((m) => (
                      <tr key={`${m.provider}-${m.model}`} className="border-b border-border/50 last:border-0">
                        <td className="max-w-[220px] truncate py-2 font-mono">{m.model}</td>
                        <td className="py-2 text-muted-foreground">{m.provider}</td>
                        <td className="py-2 text-right">{m.calls.toLocaleString()}</td>
                        <td className="py-2 text-right">{m.tokens_in.toLocaleString()}</td>
                        <td className="py-2 text-right">{m.tokens_out.toLocaleString()}</td>
                        <td className="py-2 text-right">{Math.round(m.avg_latency_ms)} ms</td>
                        <td className="py-2 text-right">${m.est_cost_usd.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 p-4">
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {icon}
          {label}
        </span>
        <span className="text-xl font-semibold tracking-tight">{value}</span>
        {sub && <span className="text-[11px] text-muted-foreground">{sub}</span>}
      </CardContent>
    </Card>
  );
}

function DailyBars({ byDay }: { byDay: DailyUsage[] }) {
  const maxCalls = Math.max(...byDay.map((d) => d.calls), 1);
  return (
    <div className="flex h-40 items-end gap-1.5 pt-2">
      {byDay.map((d) => (
        <div key={d.day} className="group relative flex min-w-0 flex-1 flex-col items-center justify-end">
          <span className="absolute -top-5 hidden rounded bg-foreground px-1.5 py-0.5 text-[10px] text-background group-hover:block">
            {d.calls} · {d.day.slice(5)}
          </span>
          <div
            className="w-full max-w-[28px] rounded-t bg-primary/70 transition-colors group-hover:bg-primary"
            style={{ height: `${Math.max(4, (d.calls / maxCalls) * 120)}px` }}
          />
          <span className="mt-1 truncate text-[9px] text-muted-foreground">{d.day.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
