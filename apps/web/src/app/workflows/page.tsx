"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Layers, Play, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getToken, type Template, type Workflow } from "@/lib/api";

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = React.useState<Workflow[]>([]);
  const [templates, setTemplates] = React.useState<Template[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    Promise.all([
      apiFetch<Workflow[]>("/workflows").catch(() => [] as Workflow[]),
      apiFetch<Template[]>("/workflows/templates").catch(() => [] as Template[]),
    ])
      .then(([wf, tmpl]) => {
        setWorkflows(wf);
        setTemplates(tmpl);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-12">
        <p className="text-sm text-muted-foreground">Loading workflows…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Workflows</h1>
          <p className="text-sm text-muted-foreground">Hand-build DAGs or use a template — same engine as auto-planned chats.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/workflows/builder">
            <Button>
              <Plus className="h-4 w-4" /> New workflow
            </Button>
          </Link>
        </div>
      </header>

      {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-medium">
          <Layers className="h-4 w-4" /> Templates
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id} className="flex flex-col">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t.name}</CardTitle>
                <CardDescription className="text-xs">{t.description}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto flex flex-col gap-2">
                <p className="font-mono text-xs text-muted-foreground">{t.steps.map((s) => s.agent_id).join(" → ")}</p>
                <Link href={`/workflows/builder?template=${t.id}`}>
                  <Button variant="outline" size="sm" className="w-full">
                    Use template <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-medium">
          <Clock className="h-4 w-4" /> Your workflows
        </h2>
        {workflows.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No workflows yet. Create one with the builder or ask via chat — both use the same DAG engine.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">
            {workflows.map((wf) => (
              <Card key={wf.id} className="hover:border-primary/30">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-sm">{wf.name}</CardTitle>
                      <CardDescription className="font-mono text-xs">
                        {wf.steps.length} steps · {wf.status} · {wf.id.slice(0, 8)}
                      </CardDescription>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        wf.status === "done"
                          ? "bg-emerald-500/10 text-emerald-500"
                          : wf.status === "failed"
                            ? "bg-destructive/10 text-destructive"
                            : wf.status === "running"
                              ? "bg-amber-500/10 text-amber-500"
                              : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {wf.status}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-wrap items-center gap-2">
                  <p className="flex-1 font-mono text-xs text-muted-foreground">
                    {wf.steps.map((s) => `${s.seq}:${s.agent_id}`).join(" · ")}
                  </p>
                  <Link href={`/workflows/builder?workflow=${wf.id}`}>
                    <Button variant="outline" size="sm">
                      Open
                    </Button>
                  </Link>
                  <WorkflowExecuteButton workflowId={wf.id} />
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function WorkflowExecuteButton({ workflowId }: { workflowId: string }) {
  const [pending, setPending] = React.useState(false);
  const [result, setResult] = React.useState<string | null>(null);
  async function onExecute() {
    setPending(true);
    setResult(null);
    try {
      const wf = await apiFetch<{ status: string; definition?: { synthesis?: string } }>(`/workflows/${workflowId}/execute`, {
        method: "POST",
      });
      const synth = (wf as unknown as { definition?: { synthesis?: string } }).definition?.synthesis;
      setResult(synth ? synth.slice(0, 300) : `Executed: ${wf.status}`);
    } catch (e) {
      setResult(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" onClick={onExecute} disabled={pending}>
        <Play className="h-3 w-3" />
        {pending ? "Running…" : "Run"}
      </Button>
      {result && <span className="max-w-[260px] truncate text-xs text-muted-foreground" title={result}>{result}</span>}
    </div>
  );
}
