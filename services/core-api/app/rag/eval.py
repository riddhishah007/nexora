"""Phase 29: RAG golden-set eval harness.

Pure-Python metrics (no DB/LLM required for unit scoring) + an async
evaluator that runs `retrieve` against a fixture file.

Blueprint §13 V1: after hybrid/rerank (§28), you need to *measure* whether
retrieval actually grounds answers — otherwise V1 is just vibes.

Fixture format (JSON):
[
  {"query": "What is Nexora?", "expected_chunk_ids": ["<uuid>", ...], "top_k": 5, "expected_document_id": "<uuid>" | null},
  ...
]
Metrics per case: hits, recall, precision, mrr, hit_rate, ndcg.
Aggregates: mean + per-case breakdown.

The harness works in two modes:
- offline (default, in pytest): scores pre-supplied `retrieved_ids` without touching DB/LLM.
- live (explicit `-m llm` or manual run): calls `retrieve` with a real gateway.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class GoldenCase:
    query: str
    expected_chunk_ids: list[str]
    top_k: int = 5
    expected_document_id: str | None = None


@dataclass
class CaseResult:
    query: str
    expected: list[str]
    retrieved: list[str]
    hits: int
    recall: float
    precision: float
    mrr: float
    ndcg: float
    hit_rate: float
    top_k: int


@dataclass
class EvalReport:
    cases: int
    mean_recall: float
    mean_precision: float
    mean_mrr: float
    mean_ndcg: float
    mean_hit_rate: float
    per_case: list[CaseResult]


def _ndcg(expected: list[str], retrieved: list[str]) -> float:
    """NDCG with binary relevance (1 if retrieved id is in expected)."""
    if not expected:
        return 0.0
    exp_set = set(expected)
    dcg = 0.0
    for i, rid in enumerate(retrieved, start=1):
        if rid in exp_set:
            dcg += 1.0 / math.log2(i + 1)
    # ideal: all hits at the top
    ideal_hits = min(len(expected), len(retrieved))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def score_case(expected_ids: list[str], retrieved_ids: list[str]) -> dict:
    """Score one retrieval result. Never raises."""
    try:
        exp = [str(x) for x in (expected_ids or [])]
        ret = [str(x) for x in (retrieved_ids or [])]
        if not exp:
            return {"hits": 0, "recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0, "hit_rate": 0.0}
        exp_set = set(exp)
        hits = sum(1 for rid in ret if rid in exp_set)
        recall = hits / len(exp) if exp else 0.0
        precision = hits / len(ret) if ret else 0.0
        # MRR: 1/rank of first relevant
        mrr = 0.0
        for i, rid in enumerate(ret, start=1):
            if rid in exp_set:
                mrr = 1.0 / i
                break
        return {
            "hits": hits,
            "recall": round(float(recall), 4),
            "precision": round(float(precision), 4),
            "mrr": round(float(mrr), 4),
            "ndcg": round(float(_ndcg(exp, ret)), 4),
            "hit_rate": round(1.0 if hits > 0 else 0.0, 4),
        }
    except Exception:
        return {"hits": 0, "recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0, "hit_rate": 0.0}


def load_golden(path: str | Path) -> list[GoldenCase]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("golden file must be a JSON array")
    out: list[GoldenCase] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"case {i}: must be an object")
        q = str(item.get("query") or "").strip()
        if not q:
            raise ValueError(f"case {i}: query is required")
        exp = item.get("expected_chunk_ids") or item.get("expected") or []
        if not isinstance(exp, list):
            raise ValueError(f"case {i}: expected_chunk_ids must be a list")
        # validate uuid-ish but allow any string for offline fixtures
        for eid in exp:
            if not isinstance(eid, str) or not eid.strip():
                raise ValueError(f"case {i}: expected_chunk_ids entries must be non-empty strings")
        out.append(
            GoldenCase(
                query=q,
                expected_chunk_ids=[str(x).strip() for x in exp],
                top_k=int(item.get("top_k") or 5),
                expected_document_id=str(item["expected_document_id"]).strip() if item.get("expected_document_id") else None,
            )
        )
    return out


def evaluate_offline(cases: list[GoldenCase], retrieved_by_query: dict[str, list[str]]) -> EvalReport:
    """Score without DB/LLM — caller supplies retrieved_ids per query."""
    per: list[CaseResult] = []
    for c in cases:
        ret = retrieved_by_query.get(c.query) or []
        s = score_case(c.expected_chunk_ids, ret)
        per.append(
            CaseResult(
                query=c.query,
                expected=c.expected_chunk_ids,
                retrieved=ret[: c.top_k],
                hits=int(s["hits"]),
                recall=float(s["recall"]),
                precision=float(s["precision"]),
                mrr=float(s["mrr"]),
                ndcg=float(s["ndcg"]),
                hit_rate=float(s["hit_rate"]),
                top_k=c.top_k,
            )
        )
    n = len(per) or 1
    return EvalReport(
        cases=len(per),
        mean_recall=round(sum(r.recall for r in per) / n, 4) if per else 0.0,
        mean_precision=round(sum(r.precision for r in per) / n, 4) if per else 0.0,
        mean_mrr=round(sum(r.mrr for r in per) / n, 4) if per else 0.0,
        mean_ndcg=round(sum(r.ndcg for r in per) / n, 4) if per else 0.0,
        mean_hit_rate=round(sum(r.hit_rate for r in per) / n, 4) if per else 0.0,
        per_case=per,
    )


async def evaluate_live(
    cases: list[GoldenCase],
    db,
    gateway,
    user_id: str,
) -> EvalReport:
    """Run retrieve() for each golden case and score."""
    from app.rag.service import retrieve

    per: list[CaseResult] = []
    for c in cases:
        try:
            # validate uuid for document-scoped cases early to surface fixture errors
            if c.expected_document_id:
                uuid.UUID(c.expected_document_id)
            rows = await retrieve(
                query=c.query,
                db=db,
                gateway=gateway,
                user_id=user_id,
                top_k=c.top_k,
                document_id=c.expected_document_id,
            )
            ret_ids = [r["chunk_id"] for r in rows]
        except Exception:
            ret_ids = []
        s = score_case(c.expected_chunk_ids, ret_ids)
        per.append(
            CaseResult(
                query=c.query[:120],
                expected=c.expected_chunk_ids,
                retrieved=ret_ids,
                hits=int(s["hits"]),
                recall=float(s["recall"]),
                precision=float(s["precision"]),
                mrr=float(s["mrr"]),
                ndcg=float(s["ndcg"]),
                hit_rate=float(s["hit_rate"]),
                top_k=c.top_k,
            )
        )
    n = len(per) or 1
    return EvalReport(
        cases=len(per),
        mean_recall=round(sum(r.recall for r in per) / n, 4) if per else 0.0,
        mean_precision=round(sum(r.precision for r in per) / n, 4) if per else 0.0,
        mean_mrr=round(sum(r.mrr for r in per) / n, 4) if per else 0.0,
        mean_ndcg=round(sum(r.ndcg for r in per) / n, 4) if per else 0.0,
        mean_hit_rate=round(sum(r.hit_rate for r in per) / n, 4) if per else 0.0,
        per_case=per,
    )


def report_to_dict(report: EvalReport) -> dict:
    return {
        "cases": report.cases,
        "mean_recall": report.mean_recall,
        "mean_precision": report.mean_precision,
        "mean_mrr": report.mean_mrr,
        "mean_ndcg": report.mean_ndcg,
        "mean_hit_rate": report.mean_hit_rate,
        "per_case": [asdict(c) for c in report.per_case],
    }
