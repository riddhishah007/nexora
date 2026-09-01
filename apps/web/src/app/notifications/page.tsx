"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getToken } from "@/lib/api";

type Note = { id: string; type: string; title: string; message: string; read: boolean; created_at: string; link: string | null };

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = React.useState<Note[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try { const data = await apiFetch<Note[]>("/notifications"); setItems(data); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setLoading(false); }
  }, []);
  React.useEffect(() => { if (!getToken()) { router.push("/login"); return; } load(); }, [router, load]);

  async function markAll() {
    try { await apiFetch("/notifications/read-all", { method: "POST" }); setItems((prev) => prev.map((n) => ({ ...n, read: true }))); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function markOne(id: string) {
    try { await apiFetch(`/notifications/${id}/read`, { method: "POST" }); setItems((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading notifications…</div></AppShell>;
  const unread = items.filter((n) => !n.read).length;
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Bell className="h-5 w-5" /> Notifications</h1>
            <p className="text-sm text-muted-foreground">{unread} unread · workflow completions, approval decisions, security alerts</p>
          </div>
          <Button variant="outline" size="sm" onClick={markAll} disabled={unread === 0}><CheckCheck className="h-4 w-4" /> Mark all read</Button>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        {items.length === 0 ? <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No notifications yet — run a workflow or decide an approval to generate one.</CardContent></Card> : (
          <div className="grid gap-3">
            {items.map((n) => (
              <Card key={n.id} className={n.read ? "opacity-70" : "border-primary/30"}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm">{n.title}</CardTitle>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${n.read ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary"}`}>{n.read ? "read" : "unread"} · {n.type}</span>
                  </div>
                </CardHeader>
                <CardContent className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">{n.message}</p>
                  {!n.read && <Button size="sm" variant="ghost" onClick={() => markOne(n.id)}>Mark read</Button>}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
