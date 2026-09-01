"use client";
import * as React from "react";
import Link from "next/link";
import { Store, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, type Template } from "@/lib/api";

export default function MarketplacePage() {
  const [templates, setTemplates] = React.useState<Template[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    apiFetch<Template[]>("/workflows/templates")
      .then(setTemplates)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <AppShell><div className="mx-auto max-w-6xl px-6 py-12 text-sm text-muted-foreground">Loading marketplace…</div></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Store className="h-5 w-5" /> Marketplace</h1>
          <p className="text-sm text-muted-foreground">Workflow templates — start pre-wired, then customize in the builder.</p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id} className="flex flex-col hover:border-primary/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t.name}</CardTitle>
                <CardDescription className="text-xs">{t.description}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto flex flex-col gap-3">
                <p className="font-mono text-xs text-muted-foreground">{t.steps.map((s) => s.agent_id).join(" → ")}</p>
                <Link href={`/workflows/builder?template=${t.id}`}>
                  <Button variant="outline" size="sm" className="w-full">Open in builder <ArrowRight className="h-3 w-3" /></Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
