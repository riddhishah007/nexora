"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { Files, Upload, FileText } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getToken, type DocumentInfo } from "@/lib/api";

export default function FilesPage() {
  const router = useRouter();
  const [docs, setDocs] = React.useState<DocumentInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    try {
      const data = await apiFetch<DocumentInfo[]>("/documents");
      setDocs(data);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, []);

  React.useEffect(() => { if (!getToken()) { router.push("/login"); return; } load(); }, [router, load]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getToken();
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${base}/documents`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  if (loading) return <AppShell><div className="mx-auto max-w-5xl px-6 py-12 text-sm text-muted-foreground">Loading files…</div></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Files className="h-5 w-5" /> Files</h1>
            <p className="text-sm text-muted-foreground">Upload PDFs, CSV, XLSX, TXT — then ingest to RAG for grounded answers.</p>
          </div>
          <div>
            <input ref={fileRef} type="file" className="hidden" onChange={onUpload} accept=".pdf,.csv,.xlsx,.txt,.docx" />
            <Button onClick={() => fileRef.current?.click()} disabled={uploading}><Upload className="h-4 w-4" /> {uploading ? "Uploading…" : "Upload"}</Button>
          </div>
        </header>
        {error && <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        {docs.length === 0 ? (
          <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No files yet. Upload a PDF or CSV to get started. Use RAG to ask questions over them.</CardContent></Card>
        ) : (
          <div className="grid gap-3">
            {docs.map((d) => (
              <Card key={d.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm"><FileText className="h-4 w-4" /> {d.original_filename}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap items-center gap-2 font-mono text-xs text-muted-foreground">
                  <span>{d.content_type}</span><span>·</span><span>{(d.size_bytes / 1024).toFixed(1)} KB</span><span>·</span><span>{d.page_count ?? "—"} pages</span><span>·</span><span className="rounded-full bg-muted px-2 py-0.5">{d.status}</span><span className="ml-auto">{d.id.slice(0, 8)}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
