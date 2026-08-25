"""Unit tests for Phase 26 cost estimation."""

from decimal import Decimal

from app.llm.pricing import _DEFAULT_TABLE, estimate_cost


def test_known_model_uses_table_rates():
    # qwen: (0.10 in, 0.30 out) per 1M
    cost = estimate_cost("groq", "qwen/qwen3.6-27b", 1_000_000, 0)
    assert cost == Decimal("0.100000")
    cost = estimate_cost("groq", "qwen/qwen3.6-27b", 0, 500_000)
    assert cost == Decimal("0.150000")


def test_unknown_model_falls_back_to_wildcard():
    cost = estimate_cost("groq", "totally-unknown-model", 1_000_000, 1_000_000)
    wild = _DEFAULT_TABLE["*"]
    expected = Decimal(str(round(wild[0] + wild[1], 6)))
    assert cost == expected


def test_zero_tokens_zero_cost():
    assert estimate_cost("groq", "qwen", 0, 0) == Decimal("0")


def test_substring_match_case_insensitive():
    cost = estimate_cost("gemini", "models/GeMini-2.0-flash", 1_000_000, 0)
    assert cost == Decimal("0.100000")


def test_never_raises_garbage_input():
    assert isinstance(estimate_cost("x", None, -5, -5), Decimal)
