"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bot, Database, LogOut, MessageSquare, Workflow, GitBranch, BarChart3, FolderKanban, Files, BotIcon, Shield, Store, History, BookOpen, Bell, CheckCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { clearToken, getToken } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/files", label: "Files", icon: Files },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/workflows", label: "Workflows", icon: Workflow },
  { href: "/workflows/builder", label: "Builder", icon: GitBranch },
  { href: "/agents", label: "Agents", icon: BotIcon },
  { href: "/rag", label: "RAG", icon: Database },
  { href: "/security", label: "Security", icon: Shield },
  { href: "/history", label: "History", icon: History },
  { href: "/approvals", label: "Approvals", icon: CheckCircle },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/marketplace", label: "Marketplace", icon: Store },
  { href: "/dashboard", label: "Usage", icon: BarChart3 },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  const authed = typeof window !== "undefined" ? Boolean(getToken()) : true;

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {/* Sidebar - desktop */}
      <aside className="hidden w-[220px] shrink-0 flex-col border-r border-border bg-card/30 md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <Link href="/" className="flex items-center gap-2">
            <Logo />
          </Link>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV.map((item) => {
            const active = pathname === item.href || (item.href !== "/chat" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                  active ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <div className="mb-2 rounded-md border border-border bg-background/50 p-2.5">
            <p className="flex items-center gap-1.5 text-xs font-medium">
              <Bot className="h-3.5 w-3.5 text-primary" /> How to use
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              Start in <span className="font-medium text-foreground">Chat</span> — one command runs many agents. Build repeats in{" "}
              <span className="font-medium text-foreground">Workflows</span>, inspect grounding in{" "}
              <span className="font-medium text-foreground">RAG</span>.
            </p>
          </div>
          {authed ? (
            <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-muted-foreground" onClick={onLogout}>
              <LogOut className="h-4 w-4" /> Sign out
            </Button>
          ) : (
            <Link href="/login" className="block">
              <Button variant="outline" size="sm" className="w-full">
                Sign in
              </Button>
            </Link>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Mobile top bar */}
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-card/40 px-3 md:hidden">
          <Link href="/" className="flex items-center gap-2">
            <Logo />
          </Link>
          <nav className="ml-auto flex items-center gap-1">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-md p-2",
                    active ? "bg-accent text-foreground" : "text-muted-foreground"
                  )}
                  aria-label={item.label}
                >
                  <Icon className="h-4 w-4" />
                </Link>
              );
            })}
          </nav>
        </header>

        <div className="flex-1 overflow-y-auto bg-background">{children}</div>
      </div>
    </div>
  );
}
