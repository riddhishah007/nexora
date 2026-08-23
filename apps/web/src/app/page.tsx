import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Logo, LogoMark } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const agentRoles = [
  { name: "Search Agent", detail: "web sources, ranked + cited" },
  { name: "RAG Agent", detail: "your knowledge base, grounded" },
  { name: "Coding Agent", detail: "sandboxed code execution" },
  { name: "PDF Agent", detail: "documents parsed + summarized" },
];

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
          <Logo />
          <nav className="flex items-center gap-2">
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className={cn(buttonVariants({ size: "sm" }))}
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-0 h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]"
          />
          <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center px-6 pb-20 pt-24 text-center sm:pt-32">
            <span
              className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground"
              style={{ animationDelay: "0ms" }}
            >
              <LogoMark className="h-3.5 w-3.5" />
              Multi-agent orchestration platform
            </span>

            <h1
              className="animate-fade-up mt-6 max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-6xl"
              style={{ animationDelay: "80ms" }}
            >
              One Command.
              <br />
              Many Agents.{" "}
              <span className="text-primary">One Intelligent Result.</span>
            </h1>

            <p
              className="animate-fade-up mt-6 max-w-xl text-balance text-muted-foreground sm:text-lg"
              style={{ animationDelay: "160ms" }}
            >
              Issue a single natural-language command. Nexora plans the work,
              delegates to specialized agents, executes with real tools, and
              synthesizes one cited answer — live, as it happens.
            </p>

            <div
              className="animate-fade-up mt-8 flex items-center gap-3"
              style={{ animationDelay: "240ms" }}
            >
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
                Create free account
                <ArrowRight />
              </Link>
              <Link
                href="/login"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
              >
                Sign in
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto w-full max-w-4xl px-6 pb-24">
          <div className="rounded-lg border border-border bg-card/60 p-8 sm:p-10">
            <AgentNetworkDiagram />
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {agentRoles.map((role) => (
                <div
                  key={role.name}
                  className="rounded-md border border-border bg-background/40 p-4"
                >
                  <p className="font-mono text-sm font-medium">{role.name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {role.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} Nexora</span>
          <span className="font-mono">Phase 3 · frontend foundation</span>
        </div>
      </footer>
    </div>
  );
}

function AgentNetworkDiagram() {
  const agents = [
    { x: 60, y: 30 },
    { x: 260, y: 30 },
    { x: 60, y: 130 },
    { x: 260, y: 130 },
  ];

  return (
    <svg
      viewBox="0 0 320 160"
      className="mx-auto h-auto w-full max-w-md"
      role="img"
      aria-label="Diagram: an orchestrator node connected to four agent nodes"
    >
      {agents.map((a) => (
        <line
          key={`${a.x}-${a.y}`}
          x1="160"
          y1="80"
          x2={a.x}
          y2={a.y}
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1"
        />
      ))}
      {agents.map((a) => (
        <circle
          key={`c-${a.x}-${a.y}`}
          cx={a.x}
          cy={a.y}
          r="10"
          fill="#111118"
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="1"
        />
      ))}
      <circle cx="160" cy="80" r="26" fill="#7b68ee" opacity="0.15" />
      <circle cx="160" cy="80" r="14" fill="#7b68ee" opacity="0.35" />
      <circle
        cx="160"
        cy="80"
        r="18"
        fill="none"
        stroke="#7b68ee"
        strokeWidth="1.5"
        className="origin-center animate-pulse-ring"
        style={{ transformBox: "fill-box", transformOrigin: "center" }}
      />
      <circle cx="160" cy="80" r="9" fill="#7b68ee" />
    </svg>
  );
}
