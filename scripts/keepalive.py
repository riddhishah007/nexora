#!/usr/bin/env python3
"""Keep Render Free awake — hits /health every call.

- For local cron: `python scripts/keepalive.py --base https://nexora-core-api.onrender.com`
- For CI cron: see .github/workflows/keepalive.yml (runs every 10 min, uses this script).
- Sleeps 15 min on Free tier (docs/DEPLOYMENT.md:45) cause ~60s cold start; a ping every 10 min
  keeps the merged worker alive but consumes ~720h/mo (within 750h Free quota for 1 service).
  Disable the workflow if you prefer cold starts and saving hours.

Exit 0 on healthy, 1 on fail (so the Action shows red if Render is down).
"""
from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://nexora-core-api.onrender.com")
    p.add_argument("--timeout", type=float, default=20.0)
    args = p.parse_args()
    base = args.base.rstrip("/")
    try:
        r = httpx.get(f"{base}/health", timeout=args.timeout)
        r.raise_for_status()
        j = r.json()
        assert j.get("status") == "ok", j
        rid = r.headers.get("x-request-id") or r.headers.get("X-Request-ID") or "-"
        print(f"[keepalive] {base}/health ok {j} X-Request-ID={rid}")
        # also warm metrics once so Prometheus counters are visible
        m = httpx.get(f"{base}/metrics", timeout=args.timeout)
        if "nexora_build_info" not in m.text:
            print("[keepalive] metrics missing build_info", file=sys.stderr)
            return 1
        print("[keepalive] metrics ok")
        return 0
    except Exception as e:
        print(f"[keepalive] FAIL {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
