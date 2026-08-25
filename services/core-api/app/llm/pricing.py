"""Phase 26 — LLM cost estimation.

`estimated_cost` in api_usage was hardcoded to 0; this module computes a
per-call estimate from a model→(input,output) USD-per-1M-tokens table.

Rates are ROUGH ESTIMATES for pay-as-you-go list prices and drift over time.
Override via env `LLM_COST_TABLE_JSON`, e.g.:
    {"qwen": [0.10, 0.30], "llama": [0.05, 0.20], "*": [0.10, 0.30]}
Keys match as case-insensitive substrings of the model id; "*" is the fallback.
"""

import json
from decimal import Decimal

from app.config import settings

# (input $/1M tok, output $/1M tok)
_DEFAULT_TABLE: dict[str, tuple[float, float]] = {
    "qwen": (0.10, 0.30),
    "llama": (0.08, 0.25),
    "gemma": (0.06, 0.20),
    "gemini": (0.10, 0.40),
    "*": (0.10, 0.30),
}


def _table() -> dict[str, tuple[float, float]]:
    raw = getattr(settings, "llm_cost_table_json", None)
    if not raw:
        return _DEFAULT_TABLE
    try:
        parsed = json.loads(raw)
        out: dict[str, tuple[float, float]] = {}
        for k, v in parsed.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                out[str(k).lower()] = (float(v[0]), float(v[1]))
        if "*" not in out:
            out["*"] = _DEFAULT_TABLE["*"]
        return out
    except Exception:
        return _DEFAULT_TABLE


def estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Estimated USD cost for one LLM call. Never raises."""
    try:
        model_l = (model or "").lower()
        table = _table()
        rates = None
        for key, value in table.items():
            if key != "*" and key in model_l:
                rates = value
                break
        if rates is None:
            rates = table.get("*", (0.0, 0.0))
        cost_in = (tokens_in / 1_000_000) * rates[0]
        cost_out = (tokens_out / 1_000_000) * rates[1]
        return Decimal(str(round(cost_in + cost_out, 6)))
    except Exception:
        return Decimal("0")
