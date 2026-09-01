"use client";
import Link from "next/link";
import { Database, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function KnowledgePage() {
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Database className="h-5 w-5" /> Knowledge</h1>
          <p className="text-sm text-muted-foreground">Your ingested PDFs as a knowledge base — manage files and inspect retrieval.</p>
        </header>
        <div className="grid gap-3 sm:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-sm">Files</CardTitle><CardDescription className="text-xs">Upload PDFs, CSV, XLSX, TXT</CardDescription></CardHeader>
            <CardContent><Link href="/files"><Button variant="outline" size="sm" className="w-full">Go to Files <ArrowRight className="h-3 w-3" /></Button></Link></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-sm">RAG Inspector</CardTitle><CardDescription className="text-xs">Score-sorted retrieval with distance + α echo</CardDescription></CardHeader>
            <CardContent><Link href="/rag"><Button variant="outline" size="sm" className="w-full">Open RAG <ArrowRight className="h-3 w-3" /></Button></Link></CardContent>
          </Card>
        </div>
        <Card>
          <CardContent className="py-6 text-sm text-muted-foreground">Upload in <span className="font-medium text-foreground">Files</span>, then ingest via <span className="font-mono text-xs">POST /api/v1/rag/ingest</span> (or the RAG queue path), and test grounding in <span className="font-medium text-foreground">RAG</span> before chatting — the RAG Agent will cite these chunks.</CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
