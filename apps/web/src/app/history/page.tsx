"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { History } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch, getToken, type ConversationSummary } from "@/lib/api";

export default function HistoryPage() {
  const router = useRouter();
  const [convs, setConvs] = React.useState<ConversationSummary[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    apiFetch<ConversationSummary[]>("/conversations")
      .then(setConvs)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [router]);
  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading history…</div></AppShell>;
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><History className="h-5 w-5" /> History</h1>
          <p className="text-sm text-muted-foreground">All your chat conversations — resume any thread in Chat.</p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        {convs.length === 0 ? <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No conversations yet — send your first command in Chat.</CardContent></Card> : (
          <div className="grid gap-3">
            {convs.map((c) => (
              <Card key={c.id} className="hover:border-primary/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{c.title || "Untitled"}</CardTitle>
                  <CardDescription className="font-mono text-xs">{new Date(c.created_at).toLocaleString()} · {c.id.slice(0, 8)}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href={`/chat?conversation=${c.id}`}><Button variant="outline" size="sm">Open in Chat</Button></Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
