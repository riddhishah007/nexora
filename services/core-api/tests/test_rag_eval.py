"""Phase 29: golden-set eval harness scoring + fixture loading."""

from pathlib import Path

import pytest

from app.rag.eval import evaluate_offline, load_golden, score_case


def test_score_case_perfect_recall():
    exp = ["a", "b", "c"]
    ret = ["a", "b", "c", "d"]
    s = score_case(exp, ret)
    assert s["hits"] == 3
    assert s["recall"] == 1.0
    assert s["precision"] == 0.75
    assert s["mrr"] == 1.0
    assert s["ndcg"] == 1.0
    assert s["hit_rate"] == 1.0


def test_score_case_partial_mrr_and_ndcg():
    exp = ["a", "b"]
    ret = ["x", "a", "y", "b"]  # first hit at rank 2
    s = score_case(exp, ret)
    assert s["hits"] == 2
    assert s["recall"] == 1.0
    assert s["mrr"] == 0.5
    assert 0.0 < s["ndcg"] < 1.0


def test_score_case_no_hits():
    s = score_case(["a"], ["x", "y"])
    assert s["hits"] == 0
    assert s["recall"] == 0.0
    assert s["mrr"] == 0.0
    assert s["ndcg"] == 0.0
    assert s["hit_rate"] == 0.0


def test_score_case_empty_expected():
    s = score_case([], ["a"])
    assert s["recall"] == 0.0
    assert s["precision"] == 0.0


def test_score_case_never_raises():
    assert isinstance(score_case(None, None), dict)  # type: ignore


def test_load_golden_small_fixture():
    p = Path(__file__).parent / "fixtures" / "rag_golden_small.json"
    cases = load_golden(p)
    assert len(cases) == 3
    assert cases[0].query == "What is Nexora?"
    assert cases[0].top_k == 5


def test_load_golden_validation():
    import tempfile
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump([{"expected_chunk_ids": ["a"]}], f)
        fname = f.name
    with pytest.raises(ValueError, match="query is required"):
        load_golden(fname)


def test_evaluate_offline_aggregates():
    from app.rag.eval import GoldenCase

    cases = [GoldenCase(query="q1", expected_chunk_ids=["a"], top_k=2), GoldenCase(query="q2", expected_chunk_ids=["b"], top_k=2)]
    report = evaluate_offline(cases, {"q1": ["a"], "q2": ["x"]})
    assert report.cases == 2
    assert report.mean_recall == 0.5
    assert report.mean_hit_rate == 0.5
    assert len(report.per_case) == 2
