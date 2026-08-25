"use client";

import dynamic from "next/dynamic";

const ChatWorkspace = dynamic(() => import("./ChatWorkspace").then((m) => m.default), {
  ssr: false,
  loading: () => <div className="flex h-[60vh] items-center justify-center text-sm text-muted-foreground">Loading chat…</div>,
});

export default function ChatPage() {
  return <ChatWorkspace />;
}
