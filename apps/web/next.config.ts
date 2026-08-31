import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone for Docker (docker-compose.yml) — Vercel handles its own output
  ...(process.env.VERCEL !== "1" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
