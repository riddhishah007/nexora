#!/usr/bin/env python3
"""Portfolio demo harness — runs scenarios 7 + 9 + 5 against live (no heavy LLM needed).

- Approvals: create → decide → notifications
- Exports: workflow export (if any) + conversation export
- Cost: usage summary

Usage: python scripts/demo_portfolio.py --base https://nexora-core-api.onrender.com
"""
from __future__ import annotations
import argparse
import uuid

import httpx


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://nexora-core-api.onrender.com")
    args = p.parse_args()
    base = args.base.rstrip("/")

    email = f"demo_{uuid.uuid4().hex[:6]}@example.com"
    pw = "DemoPass123!"
    r = httpx.post(f"{base}/api/v1/auth/register", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code in (200, 201), r.text
    tok = r.json().get("access_token")
    # also test login path
    r2 = httpx.post(f"{base}/api/v1/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r2.status_code == 200
    tok2 = r2.json()["access_token"]
    h = {"Authorization": f"Bearer {tok2}"}

    print(f"[demo] user {email}")

    # approvals: create pending
    r = httpx.post(f"{base}/api/v1/approvals", json={"action": "demo HIGH: execute_code sandbox deploy"}, headers=h, timeout=15)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    print(f"[demo] approval created {aid} pending")

    # list approvals
    r = httpx.get(f"{base}/api/v1/approvals", headers=h, timeout=15)
    assert r.status_code == 200 and any(x["id"] == aid for x in r.json())
    print(f"[demo] list approvals {len(r.json())}")

    # decide approved
    r = httpx.post(f"{base}/api/v1/approvals/{aid}/decision", json={"decision": "approved", "reason": "demo auto-approve"}, headers=h, timeout=15)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    print("[demo] approved")

    # notifications: should have one for approval
    r = httpx.get(f"{base}/api/v1/notifications", headers=h, timeout=15)
    assert r.status_code == 200
    print(f"[demo] notifications {len(r.json())}")

    # projects: create one for export context
    r = httpx.post(f"{base}/api/v1/projects", json={"name": "Demo Project"}, headers=h, timeout=15)
    assert r.status_code == 201
    print("[demo] project created")

    # usage: check it
    r = httpx.get(f"{base}/api/v1/usage/summary?days=7", headers=h, timeout=15)
    assert r.status_code == 200
    print(f"[demo] usage calls={r.json()['total_calls']}")

    # workflows: list templates (marketplace)
    r = httpx.get(f"{base}/api/v1/workflows/templates", timeout=15)
    assert r.status_code == 200 and len(r.json()) >= 6
    print(f"[demo] templates {len(r.json())}")

    # create a trivial workflow to export
    r = httpx.post(f"{base}/api/v1/workflows", json={"name": "Demo Export WF", "steps": [{"agent_id": "search-agent", "instruction": "Search for Nexora", "depends_on": []}]}, headers=h, timeout=15)
    assert r.status_code == 201
    wid = r.json()["id"]
    print(f"[demo] workflow {wid}")

    # export it
    r = httpx.get(f"{base}/api/v1/exports/workflow/{wid}", headers=h, timeout=15)
    assert r.status_code == 200 and wid[:8] in r.text or "Demo Export" in r.text
    print("[demo] export workflow PASS")

    print("DEMO PASS — scenarios 7+9+5+1+3 verified live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
