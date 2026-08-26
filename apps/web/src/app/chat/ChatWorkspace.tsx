"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, Check, Loader2, Plus, Send, User as UserIcon, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch, getToken, type ChatMessage, type ChatResponse, type ConversationDetail, type ConversationSummary, type Workflow } from "@/lib/api";
import { useWorkflowStream, type StepRunStatus } from "@/lib/useWorkflowStream";
import { cn } from "@/lib/utils";

type SeedStep = { seq: number; agent_id: string; instruction: string; status: string };

type PendingRun = { workflowId: string; conversationId: string; seedSteps: SeedStep[] };

export default function ChatPage() {
  const router = useRouter();
  const params = useSearchParams();
  const activeId = params.get("c");

  const [conversations, setConversations] = React.useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = React.useState<ConversationDetail | null>(null);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [pendingRun, setPendingRun] = React.useState<PendingRun | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  const authed = React.useMemo(() => Boolean(getToken()), []);
  const stream = useWorkflowStream(pendingRun?.workflowId ?? null, Boolean(pendingRun));

  React.useEffect(() => {
    if (!authed) router.push("/login");
  }, [authed, router]);

  // conversation list
  React.useEffect(() => {
    if (!authed) return;
    apiFetch<ConversationSummary[]>("/conversations")
      .then(setConversations)
      .catch(() => {});
  }, [authed, sending, pendingRun]);

  // active thread
  React.useEffect(() => {
    if (!activeId) {
      setConversation(null);
      return;
    }
    if (sending && pendingRun && pendingRun.conversationId === activeId) return; // already loaded optimistically
    apiFetch<ConversationDetail>(`/conversations/${activeId}`)
      .then(setConversation)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [activeId, sending, pendingRun]);

  function finishRun(detail: ConversationDetail | null) {
    if (detail) setConversation(detail);
    setPendingRun(null);
    setSending(false);
  }

  // run finished → load persisted assistant message and stop streaming
  const convIdRef = React.useRef<string | null>(conversation?.id ?? null);
  React.useEffect(() => {
    convIdRef.current = conversation?.id ?? null;
  }, [conversation]);
  React.useEffect(() => {
    if (!stream.finalReady || !pendingRun) return;
    const cid = convIdRef.current || pendingRun.conversationId;
    apiFetch<ConversationDetail>(`/conversations/${cid}`)
      .then(finishRun)
      .catch(() => finishRun(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.finalReady]);

  // polling fallback in case the WS stream is unavailable
  React.useEffect(() => {
    if (!pendingRun) return;
    const t = setInterval(async () => {
      try {
        const detail = await apiFetch<ConversationDetail>(`/conversations/${pendingRun.conversationId}`);
        const last = detail.messages[detail.messages.length - 1];
        if (last?.role === "assistant" && last.workflow_id === pendingRun.workflowId) finishRun(detail);
      } catch {}
    }, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingRun?.workflowId]);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages.length, sending]);

  async function send() {
    const message = input.trim();
    if (!message || sending) return;
    setInput("");
    setError(null);
    setSending(true);
    try {
      const res = await apiFetch<ChatResponse>("/chat/start", {
        method: "POST",
        body: JSON.stringify({ message, conversation_id: activeId || null }),
      });
      const seedSteps: SeedStep[] = res.steps.map((s) => ({
        seq: s.seq,
        agent_id: s.agent_id,
        instruction: s.instruction,
        status: s.status,
      }));
      if (!activeId || res.conversation_id !== activeId) {
        // new thread: load it immediately (user message is already persisted)
        try {
          const detail = await apiFetch<ConversationDetail>(`/conversations/${res.conversation_id}`);
          setConversation(detail);
        } catch {}
        router.replace(`/chat?c=${res.conversation_id}`);
      }
      setPendingRun({ workflowId: res.workflow_id, conversationId: res.conversation_id, seedSteps });
    } catch (e) {
      setSending(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex h-dvh">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card/30 md:flex">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <Link href="/chat" className="text-sm font-semibold">
            Nexora
          </Link>
          <Link href="/workflows" className="text-xs text-muted-foreground hover:text-foreground">
            Workflows
          </Link>
          <Link href="/rag" className="text-xs text-muted-foreground hover:text-foreground">
            RAG
          </Link>
          <Link href="/dashboard" className="text-xs text-muted-foreground hover:text-foreground">
            Usage
          </Link>
        </div>
        <div className="p-3">
          <Button variant="outline" size="sm" className="w-full" onClick={() => router.push("/chat")}>
            <Plus className="h-4 w-4" /> New chat
          </Button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
          {conversations.map((c) => (
            <Link
              key={c.id}
              href={`/chat?c=${c.id}`}
              className={cn(
                "block truncate rounded-md px-2 py-1.5 text-xs hover:bg-accent",
                c.id === activeId ? "bg-accent font-medium" : "text-muted-foreground"
              )}
              title={c.title}
            >
              {c.title}
            </Link>
          ))}
          {conversations.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground">No conversations yet.</p>
          )}
        </nav>
      </aside>

      {/* Thread */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-border bg-card/50 px-4 py-2 md:hidden">
          <Link href="/chat" className="text-sm font-semibold">Nexora</Link>
          <Link href="/workflows" className="ml-auto text-xs text-muted-foreground">Workflows</Link>
        </header>

        <div className="flex-1 overflow-y-auto">
          {!conversation ? (
            <EmptyState />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
              <h1 className="truncate text-lg font-semibold tracking-tight">{conversation.title}</h1>
              {conversation.messages.map((m) => (
                <MessageRow key={m.id} message={m} />
              ))}
              {sending && pendingRun && (
                <PendingRunBubble
                  pending={pendingRun}
                  statuses={stream.stepStatus}
                  connected={stream.connected}
                  synthesis={stream.synthesis}
                />
              )}
              {sending && !pendingRun && <PendingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-border bg-card/40 p-3">
          {error && (
            <p className="mx-auto mb-2 max-w-3xl rounded-md border border-destructive/50 bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
              {error}
            </p>
          )}
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={Math.min(5, Math.max(1, input.split("\n").length))}
              placeholder="Give the orchestrator a command… e.g. “Research HTTP/3 adoption and write an executive brief”"
              className="max-h-40 min-h-[42px] flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
              disabled={sending}
            />
            <Button size="icon" onClick={send} disabled={sending || !input.trim()} aria-label="Send" className="h-[42px] w-[42px] shrink-0">
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <span className="rounded-full bg-primary/10 p-3">
        <Bot className="h-6 w-6 text-primary" />
      </span>
      <h2 className="text-lg font-semibold tracking-tight">One command. Many agents.</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        Ask anything — the planner picks the right agents (search, RAG, research, data,
        code, writer), runs them in parallel where it can, and synthesizes one cited answer.
      </p>
    </div>
  );
}

function PendingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <Avatar role="assistant" />
      <div className="mt-1 flex items-center gap-2 rounded-xl bg-muted px-3 py-2 text-xs text-muted-foreground">
        <span className="flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:0ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:150ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:300ms]" />
        </span>
        Planning · running agents · synthesizing…
      </div>
    </div>
  );
}

function PendingRunBubble({
  pending,
  statuses,
  connected,
  synthesis,
}: {
  pending: PendingRun;
  statuses: Record<number, StepRunStatus>;
  connected: boolean;
  synthesis: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <Avatar role="assistant" />
      <div className="min-w-0 max-w-[85%]">
        <div className="mb-1.5 flex flex-wrap items-center gap-1">
          {pending.seedSteps.map((step) => {
            const st = statuses[step.seq] || (step.status === "pending" ? "pending" : undefined);
            return (
              <span
                key={step.seq}
                title={`${step.agent_id}: ${step.instruction}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]",
                  CHIP_STYLES[st === "done" ? "done" : st === "failed" ? "failed" : st === "running" || st === "selected" ? "running" : ""] ||
                    "border-border bg-muted text-muted-foreground"
                )}
              >
                {st === "running" && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                {st === "done" && <Check className="h-2.5 w-2.5" />}
                {st === "failed" && <X className="h-2.5 w-2.5" />}
                {step.seq}. {step.agent_id}
              </span>
            );
          })}
        </div>
        {synthesis ? (
          <div className="inline-block rounded-tl-sm rounded-2xl bg-muted px-4 py-2.5 text-sm">
            <MarkdownLite text={synthesis} />
            <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-primary align-middle" />
          </div>
        ) : (
          <div className="inline-flex items-center gap-2 rounded-xl bg-muted px-3 py-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin text-primary" />
            {connected ? "Agents working…" : "Connecting to live stream…"}
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  return role === "assistant" ? (
    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
      <Bot className="h-4 w-4 text-primary" />
    </span>
  ) : (
    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary">
      <UserIcon className="h-4 w-4 text-secondary-foreground" />
    </span>
  );
}

function MessageRow({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <Avatar role={isUser ? "user" : "assistant"} />
      <div className={cn("min-w-0 max-w-[85%]", isUser && "text-right")}>
        {!isUser && message.workflow_id && <AgentChips workflowId={message.workflow_id} />}
        <div
          className={cn(
            "inline-block rounded-2xl px-4 py-2.5 text-sm",
            isUser ? "rounded-tr-sm bg-primary text-primary-foreground" : "rounded-tl-sm bg-muted"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-left">{message.content}</p>
          ) : (
            <MarkdownLite text={message.content} />
          )}
        </div>
      </div>
    </div>
  );
}

const CHIP_STYLES: Record<string, string> = {
  done: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
  running: "border-primary/40 bg-primary/10 text-primary",
};

function AgentChips({ workflowId }: { workflowId: string }) {
  const [steps, setSteps] = React.useState<Workflow["steps"] | null>(null);

  React.useEffect(() => {
    let alive = true;
    apiFetch<Workflow>(`/workflows/${workflowId}`)
      .then((wf) => {
        if (alive) setSteps(wf.steps);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [workflowId]);

  if (!steps || steps.length === 0) return null;
  return (
    <div className="mb-1.5 flex flex-wrap gap-1">
      {steps.map((s) => (
        <span
          key={s.seq}
          title={`${s.agent_id}: ${s.instruction}`}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]",
            CHIP_STYLES[s.status] || "border-border bg-muted text-muted-foreground"
          )}
        >
          {s.status === "done" ? <Check className="h-2.5 w-2.5" /> : s.status === "failed" ? <X className="h-2.5 w-2.5" /> : null}
          {s.seq}. {s.agent_id}
        </span>
      ))}
    </div>
  );
}

/** Minimal markdown: code fences, headings, bullets, numbered lists, bold, inline code. */
function MarkdownLite({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;
  let key = 0;

  function renderInline(s: string): React.ReactNode[] {
    const parts: React.ReactNode[] = [];
    const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(s))) {
      if (m.index > last) parts.push(s.slice(last, m.index));
      const tok = m[0];
      if (tok.startsWith("**")) parts.push(<strong key={`b${key++}`}>{tok.slice(2, -2)}</strong>);
      else
        parts.push(
          <code key={`c${key++}`} className="rounded bg-background/70 px-1 py-0.5 font-mono text-[0.85em]">
            {tok.slice(1, -1)}
          </code>
        );
      last = m.index + tok.length;
    }
    if (last < s.length) parts.push(s.slice(last));
    return parts;
  }

  while (i < lines.length) {
    const line = lines[i];

    if (line.trimStart().startsWith("```")) {
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        buf.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      blocks.push(
        <pre key={key++} className="my-2 overflow-x-auto rounded-lg bg-background/80 p-3 font-mono text-xs">
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      const cls = level === 1 ? "text-base font-semibold mt-3 mb-1" : level === 2 ? "text-sm font-semibold mt-3 mb-1" : "text-sm font-medium mt-2 mb-0.5";
      blocks.push(
        <p key={key++} className={cls}>
          {renderInline(h[2])}
        </p>
      );
      i += 1;
      continue;
    }

    if (/^\s*[-*•]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*•]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ul key={key++} className="my-1.5 list-disc space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it)}</li>
          ))}
        </ul>
      );
      continue;
    }

    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ol key={key++} className="my-1.5 list-decimal space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it)}</li>
          ))}
        </ol>
      );
      continue;
    }

    if (line.trim() === "") {
      blocks.push(<div key={key++} className="h-2" />);
      i += 1;
      continue;
    }

    // paragraph: gather until blank line or special block
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].trimStart().startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[i]) &&
      !/^\s*[-*•]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={key++} className="whitespace-pre-wrap break-words leading-relaxed">
        {renderInline(para.join("\n"))}
      </p>
    );
  }

  return <div className="space-y-0.5">{blocks}</div>;
}
