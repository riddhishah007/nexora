"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Check, X, Clock } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch, getToken } from "@/lib/api";

type Approval = { id: string; action: string; agent_id: string | null; workflow_id: string | null; status: string; payload: unknown; created_at: string };

export default function ApprovalsPage() {
  const router = useRouter();
  const [items, setItems] = React.useState<Approval[]>([]);
  const [action, setAction] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try { const data = await apiFetch<Approval[]>("/approvals"); setItems(data); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setLoading(false); }
  }, []);
  React.useEffect(() => { if (!getToken()) { router.push("/login"); return; } load(); }, [router, load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!action.trim()) return;
    try {
      const a = await apiFetch<Approval>("/approvals", { method: "POST", body: JSON.stringify({ action: action.trim() }) });
      setItems((prev) => [a, ...prev]); setAction("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function decide(id: string, decision: "approved" | "rejected") {
    try {
      const a = await apiFetch<Approval>(`/approvals/${id}/decision`, { method: "POST", body: JSON.stringify({ decision }) });
      setItems((prev) => prev.map((x) => x.id === id ? a : x));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading approvals…</div></AppShell>;
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><ShieldCheck className="h-5 w-5" /> Approvals</h1>
          <p className="text-sm text-muted-foreground">HITL gate for HIGH-trust tool actions — approve or reject. Blueprint §12 / §14 <span className="font-mono text-xs">POST /approvals/{`{id}`}/decision</span></p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Request approval (demo)</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="flex gap-2">
              <Input value={action} onChange={(e) => setAction(e.target.value)} placeholder="e.g. execute_code: deploy sandbox --high-trust" maxLength={128} className="flex-1" />
              <Button type="submit" disabled={!action.trim()}>Request</Button>
            </form>
          </CardContent>
        </Card>
        {items.length === 0 ? <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No approvals — HIGH-trust actions will appear here for decision.</CardContent></Card> : (
          <div className="grid gap-3">
            {items.map((a) => (
              <Card key={a.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-sm">{a.action}</CardTitle>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${a.status === "pending" ? "bg-amber-500/10 text-amber-600" : a.status === "approved" ? "bg-emerald-500/10 text-emerald-600" : "bg-destructive/10 text-destructive"}`}>{a.status}</span>
                  </div>
                  <CardDescription className="font-mono text-xs">{a.agent_id || "—"} · {a.id.slice(0, 8)} · {new Date(a.created_at).toLocaleString()}</CardDescription>
                </CardHeader>
                {a.status === "pending" && (
                  <CardContent className="flex gap-2">
                    <Button size="sm" onClick={() => decide(a.id, "approved")}><Check className="h-3 w-3" /> Approve</Button>
                    <Button size="sm" variant="outline" onClick={() => decide(a.id, "rejected")}><X className="h-3 w-3" /> Reject</Button>
                  </CardContent>
                )}
                {a.status !== "pending" && <CardContent className="flex items-center gap-1 text-xs text-muted-foreground"><Clock className="h-3 w-3" /> Decided {a.status}</CardContent>}
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
