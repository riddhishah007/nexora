"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch, getToken, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const data = await apiFetch<Project[]>("/projects");
      setProjects(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
  }, [router, load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const p = await apiFetch<Project>("/projects", { method: "POST", body: JSON.stringify({ name: name.trim(), description: description.trim() || null }) });
      setProjects((prev) => [p, ...prev]);
      setName(""); setDescription("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setCreating(false); }
  }

  async function onDelete(id: string) {
    if (!confirm("Delete this project?")) return;
    try {
      await apiFetch(`/projects/${id}`, { method: "DELETE" });
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading projects…</div></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><FolderKanban className="h-5 w-5" /> Projects</h1>
          <p className="text-sm text-muted-foreground">Group your chats, workflows, and documents. Each project is isolated to your account.</p>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">New project</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q4 Research" maxLength={200} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-muted-foreground">Description (optional)</label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this for?" maxLength={2000} />
              </div>
              <Button type="submit" disabled={creating || !name.trim()}><Plus className="h-4 w-4" /> {creating ? "Creating…" : "Create"}</Button>
            </form>
          </CardContent>
        </Card>
        <section>
          <h2 className="mb-3 text-sm font-medium">Your projects ({projects.length})</h2>
          {projects.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No projects yet. Create one above.</CardContent></Card>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {projects.map((p) => (
                <Card key={p.id} className="hover:border-primary/30">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-sm">{p.name}</CardTitle>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{p.status}</span>
                    </div>
                    <CardDescription className="text-xs">{p.description || "—"}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex items-center justify-between">
                    <span className="font-mono text-xs text-muted-foreground">{new Date(p.created_at).toLocaleDateString()} · {p.id.slice(0, 8)}</span>
                    <Button variant="ghost" size="sm" onClick={() => onDelete(p.id)}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
