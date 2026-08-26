#!/usr/bin/env python3
"""Phase 33 smoke harness: checks a running Nexora stack (local or deployed).

- GET /health + X-Request-ID
- GET /metrics (prometheus text)
- GET / (docs link)
- GET /api/v1/agents (auth-guarded; expects 401 without token, 200 with if stack is up)
- POST /api/v1/auth/register + login roundtrip (ephemeral user)
- POST /api/v1/rag/search auth guard
- RAG eval offline demo

Usage:
  python scripts/smoke.py --base http://localhost:8000
  python scripts/smoke.py --base https://nexora-core-api.onrender.com --no-auth-roundtrip

Exit 0 only if every check passes/lightly skips; exit 1 on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid

import httpx


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _warn(msg: str) -> None:
    print(f"  [SKIP] {msg} (skipped)")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    p = argparse.ArgumentParser(description="Nexora smoke checks")
    p.add_argument("--base", default="http://localhost:8000", help="Core API base URL (no trailing slash, no /api prefix)")
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--no-auth-roundtrip", action="store_true", help="Skip register/login (e.g. deployed with rate limits)")
    args = p.parse_args()

    base = args.base.rstrip("/")
    ok = True

    def check_health() -> bool:
        try:
            r = httpx.get(f"{base}/health", timeout=args.timeout)
            assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
            assert r.json().get("status") == "ok"
            assert r.headers.get("x-request-id") or r.headers.get("X-Request-ID"), "missing X-Request-ID"
            _ok(f"GET /health 200 + X-Request-ID {r.headers.get('x-request-id') or r.headers.get('X-Request-ID')}")
            return True
        except Exception as e:
            _fail(f"GET /health: {e}")
            return False

    def check_metrics() -> bool:
        try:
            r = httpx.get(f"{base}/metrics", timeout=args.timeout)
            assert r.status_code == 200, f"{r.status_code}"
            assert "nexora_http_requests_total" in r.text
            assert "nexora_build_info" in r.text
            _ok("GET /metrics prometheus text")
            return True
        except Exception as e:
            _fail(f"GET /metrics: {e}")
            return False

    def check_root() -> bool:
        try:
            r = httpx.get(f"{base}/", timeout=args.timeout)
            assert r.status_code == 200
            _ok("GET / 200")
            return True
        except Exception as e:
            _fail(f"GET /: {e}")
            return False

    def check_auth_guard() -> bool:
        try:
            r = httpx.get(f"{base}/api/v1/agents", timeout=args.timeout)
            # registry is public (no auth), but /agents/run is guarded
            if r.status_code != 200:
                _fail(f"GET /api/v1/agents expected 200 (public registry), got {r.status_code} {r.text[:120]}")
                return False
            data = r.json() if r.headers.get("content-type","").startswith("application/json") else []
            _ok(f"GET /api/v1/agents 200 public ({len(data) if isinstance(data, list) else 'ok'} agents)")
            # POST /agents/run without token must be 401
            r2 = httpx.post(f"{base}/api/v1/agents/run", json={"agent_id": "search-agent", "input": {"query": "test"}}, timeout=args.timeout)
            if r2.status_code != 401:
                _fail(f"POST /agents/run without token expected 401, got {r2.status_code}")
                return False
            _ok("POST /agents/run 401 without token (guard works)")
            return True
        except Exception as e:
            _fail(f"GET /api/v1/agents guard: {e}")
            return False

    def check_rag_search_guard() -> bool:
        try:
            r = httpx.post(f"{base}/api/v1/rag/search", json={"query": "hello", "top_k": 3}, timeout=args.timeout)
            if r.status_code != 401:
                _fail(f"POST /rag/search without token expected 401, got {r.status_code}")
                return False
            _ok("POST /rag/search 401 without token")
            return True
        except Exception as e:
            _fail(f"POST /rag/search guard: {e}")
            return False

    def check_auth_roundtrip() -> bool:
        if args.no_auth_roundtrip:
            _warn("auth roundtrip")
            return True
        try:
            email = f"smoke_{uuid.uuid4().hex[:8]}@example.com"
            pw = "SmokePass123!"
            r = httpx.post(f"{base}/api/v1/auth/register", json={"email": email, "password": pw}, timeout=args.timeout)
            if r.status_code not in (200, 201):
                _fail(f"POST /auth/register {r.status_code} {r.text[:200]}")
                return False
            tok = r.json().get("access_token") or r.json().get("token")
            # login
            r2 = httpx.post(f"{base}/api/v1/auth/login", json={"email": email, "password": pw}, timeout=args.timeout)
            if r2.status_code != 200:
                _fail(f"POST /auth/login {r2.status_code}")
                return False
            tok2 = r2.json().get("access_token")
            assert tok2, "no token from login"
            # authed request
            r3 = httpx.get(f"{base}/api/v1/agents", headers={"Authorization": f"Bearer {tok2}"}, timeout=args.timeout)
            assert r3.status_code == 200, f"agents {r3.status_code}"
            _ok(f"auth register+login+agents ({email})")
            return True
        except Exception as e:
            _fail(f"auth roundtrip: {e}")
            return False

    def check_rag_eval_offline() -> bool:
        try:
            # run the offline harness in-process (no DB)
            sys.path.insert(0, "services/core-api")
            from app.rag.eval import evaluate_offline, load_golden

            cases = load_golden("services/core-api/tests/fixtures/rag_golden_small.json")
            # demo retrieved mapping
            retrieved = {c.query: c.expected_chunk_ids[:1] if "hybrid" not in c.query else [] for c in cases}
            # but perfect for Nexora
            for c in cases:
                if "Nexora" in c.query:
                    retrieved[c.query] = c.expected_chunk_ids[:]
            rep = evaluate_offline(cases, retrieved)
            assert rep.cases == 3
            _ok(f"RAG eval offline cases={rep.cases} recall={rep.mean_recall}")
            return True
        except Exception as e:
            _fail(f"RAG eval offline: {e}")
            return False

    print(f"Smoke: {base} (timeout={args.timeout}s)")
    for fn in [check_health, check_metrics, check_root, check_auth_guard, check_rag_search_guard, check_auth_roundtrip, check_rag_eval_offline]:
        if not fn():
            ok = False

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
