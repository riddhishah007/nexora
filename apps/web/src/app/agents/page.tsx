"use client";
import * as React from "react";
import { Bot, Wrench, ShieldCheck, Coins } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, type AgentInfo } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = React.useState<AgentInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    apiFetch<AgentInfo[]>("/agents")
      .then(setAgents)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <AppShell><div className="mx-auto max-w-6xl px-6 py-12 text-sm text-muted-foreground">Loading agents…</div></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Bot className="h-5 w-5" /> Agents</h1>
          <p className="text-sm text-muted-foreground">Specialist agents registered in the orchestrator. The planner picks them automatically — or you pin them in workflows.</p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <Card key={a.agent_id} className="hover:border-primary/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{a.name}</CardTitle>
                <CardDescription className="font-mono text-xs">{a.agent_id} · {a.model} · {a.version}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs leading-relaxed text-muted-foreground">{a.description}</p>
                <div className="flex flex-wrap gap-1">
                  {a.capabilities.slice(0, 4).map((c) => <span key={c} className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-medium">{c}</span>)}
                </div>
                <div className="flex items-center gap-3 pt-1 font-mono text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Wrench className="h-3 w-3" /> {a.tools.length ? a.tools.join(", ") : "no tools"}</span>
                  <span className="flex items-center gap-1"><ShieldCheck className="h-3 w-3" /> {a.permissions.length ? a.permissions.join(", ") : "none"}</span>
                  <span className="flex items-center gap-1"><Coins className="h-3 w-3" /> {a.status}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
