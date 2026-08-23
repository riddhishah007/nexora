import type { ReactNode } from "react";
import Link from "next/link";

import { Logo } from "@/components/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-[420px] w-[640px] rounded-full bg-primary/10 blur-[120px]"
      />
      <header className="relative border-b border-border">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center px-6">
          <Link href="/" aria-label="Nexora home">
            <Logo />
          </Link>
        </div>
      </header>
      <main className="relative flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
