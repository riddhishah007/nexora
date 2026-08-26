#!/usr/bin/env python3
"""Phase 30 CLI: run RAG golden-set eval (offline or live).

Usage:
  # offline demo (no DB/LLM, pure scorer):
  python scripts/rag_eval.py --offline --fixture tests/fixtures/rag_golden_small.json

  # live (needs DB + embeddings — pass a user id that owns the chunks):
  python scripts/rag_eval.py --fixture tests/fixtures/rag_golden_small.json --user-id <uuid> --live

  # JSON output for CI:
  python scripts/rag_eval.py --offline --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure app is importable when run as `python scripts/rag_eval.py`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.eval import evaluate_live, evaluate_offline, load_golden, report_to_dict


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Nexora RAG golden-set eval")
    p.add_argument("--fixture", dest="fixture", default="tests/fixtures/rag_golden_small.json", help="Path to golden JSON array")
    p.add_argument("--offline", action="store_true", help="Run offline scorer demo (no DB/LLM)")
    p.add_argument("--live", action="store_true", help="Run live retrieval (requires --user-id and a running DB)")
    p.add_argument("--user-id", dest="user_id", default=None, help="User UUID for live retrieval (must own the chunks)")
    p.add_argument("--json", dest="json_out", action="store_true", help="Output full report as JSON")
    p.add_argument("--mock-retrieved", dest="mock_retrieved", default=None, help="JSON dict of {query: [chunk_id,...]} for offline demo with custom hits")
    return p.parse_args()


def _print_report(report, json_out: bool = False) -> None:
    if json_out:
        print(json.dumps(report_to_dict(report), indent=2))
        return
    print(f"Cases: {report.cases}  recall={report.mean_recall}  precision={report.mean_precision}  mrr={report.mean_mrr}  ndcg={report.mean_ndcg}  hit_rate={report.mean_hit_rate}")
    for c in report.per_case:
        print(f"  - {c.query!r}  hits={c.hits}/{len(c.expected)}  recall={c.recall}  mrr={c.mrr}  ndcg={c.ndcg}  top_k={c.top_k}")
        if c.retrieved:
            print(f"    retrieved: {c.retrieved[:3]}")


async def _live(fixture: str, user_id: str) -> None:
    from sqlalchemy import text as _text

    from app.database import SessionFactory
    from app.llm import get_llm_gateway

    cases = load_golden(fixture)
    gw = get_llm_gateway()
    async with SessionFactory() as db:
        # quick connectivity check
        try:
            await db.execute(_text("SELECT 1"))
        except Exception as exc:
            print(f"DB not reachable: {exc}", file=sys.stderr)
            sys.exit(2)
        report = await evaluate_live(cases, db, gw, user_id)
        return report


def _offline_demo(fixture: str, mock_json: str | None):
    cases = load_golden(fixture)
    if mock_json:
        retrieved = json.loads(mock_json)
    else:
        # demo: first case hits perfectly, second partially, third misses
        retrieved = {}
        for c in cases:
            if "Nexora" in c.query:
                retrieved[c.query] = c.expected_chunk_ids[:]
            elif "hybrid" in c.query:
                retrieved[c.query] = c.expected_chunk_ids[:1]
            else:
                retrieved[c.query] = []
    return evaluate_offline(cases, retrieved)


def main() -> None:
    args = _parse_args()
    fixture = args.fixture
    if not Path(fixture).is_file():
        # try relative to app root
        alt = ROOT / fixture
        if alt.is_file():
            fixture = str(alt)
    if args.live:
        if not args.user_id:
            print("--live requires --user-id <uuid>", file=sys.stderr)
            sys.exit(2)
        report = asyncio.run(_live(fixture, args.user_id))
    else:
        report = _offline_demo(fixture, args.mock_retrieved)
    _print_report(report, json_out=args.json_out)


if __name__ == "__main__":
    main()
