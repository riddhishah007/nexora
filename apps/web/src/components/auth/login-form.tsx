"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, setToken } from "@/lib/api";

export function LoginForm() {
  const [pending, setPending] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const router = useRouter();

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const fd = new FormData(event.currentTarget as HTMLFormElement);
    const email = String(fd.get("email") || "").trim();
    const password = String(fd.get("password") || "");
    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      if (res.refresh_token) localStorage.setItem("nexora_refresh", res.refresh_token);
      router.push("/workflows");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="border-border/80 bg-card/80 backdrop-blur">
      <CardHeader>
        <CardTitle>Welcome back</CardTitle>
        <CardDescription>Sign in to your Nexora command center.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                autoComplete="current-password"
                className="pr-10"
                minLength={8}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={pending}>
            {pending && <Loader2 className="animate-spin" />}
            Sign in
          </Button>
        </form>
      </CardContent>
      <CardFooter className="flex-col gap-3 border-t border-border text-sm">
        <p className="text-muted-foreground">
          No account?{" "}
          <Link
            href="/register"
            className="text-primary underline-offset-4 hover:underline"
          >
            Create one free
          </Link>
        </p>
        <p className="text-xs text-muted-foreground/70">
          Connected to <code className="font-mono text-xs">/api/v1/auth/login</code>
        </p>
      </CardFooter>
    </Card>
  );
}
