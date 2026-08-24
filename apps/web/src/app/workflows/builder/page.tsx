"use client";

import dynamic from "next/dynamic";

const Builder = dynamic(() => import("@/components/workflow-builder/Builder").then((m) => m.Builder), {
  ssr: false,
  loading: () => <div className="flex h-[60vh] items-center justify-center text-sm text-muted-foreground">Loading builder…</div>,
});

export default function BuilderPage() {
  return <Builder />;
}
