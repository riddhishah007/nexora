"""Blueprint §25 prompt-injection defense (heuristic, pre-LLM).

Security boundary is code here, never the prompt: even if the LLM were
tricked, tool permissions are still enforced in ToolRegistry.
This detector runs *before* any agent sees the input.
"""

import re

# Each pattern's weight — sum decides risk
_PATTERNS = [
    (re.compile(r"ignore\s+(previous|all|your)\s+instructions", re.I), 3),
    (re.compile(r"disregard\s+(previous|all|your)\s+instructions", re.I), 3),
    (re.compile(r"you\s+are\s+now\s+", re.I), 2),
    (re.compile(r"system\s*prompt", re.I), 2),
    (re.compile(r"pretend\s+you\s+are", re.I), 2),
    (re.compile(r"\bDAN\b", re.I), 2),
    (re.compile(r"do\s+anything\s+now", re.I), 2),
    (re.compile(r"bypass\s+(safety|filter|restriction)", re.I), 2),
    (re.compile(r"jailbreak", re.I), 3),
    (re.compile(r"reveal\s+(your\s+)?(instructions|system|prompt)", re.I), 3),
    (re.compile(r"show\s+(me\s+)?your\s+(system|prompt|instructions)", re.I), 2),
    (re.compile(r"from\s+now\s+on\s+you\s+are", re.I), 2),
    (re.compile(r"<\|system\|>|<<SYS>>|\[INST\]|\[SYSTEM\]", re.I), 3),
    (re.compile(r"prompt\s*injection", re.I), 1),
    (re.compile(r"override\s+(safety|policy|instructions)", re.I), 2),
    (re.compile(r"act\s+as\s+(if\s+)?you\s+are", re.I), 1),
]

# Also flag obvious exfiltration attempts inside the prompt itself
_SENSITIVE_INJECTION = re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]", re.I)

def scan(text: str) -> dict:
    """Return {score, matched: [str], risk_level, should_block}."""
    if not text:
        return {"score": 0, "matched": [], "risk_level": "low", "should_block": False, "blocked": False}

    matched: list[str] = []
    score = 0
    for pat, weight in _PATTERNS:
        if pat.search(text):
            matched.append(pat.pattern[:40])
            score += weight

    if _SENSITIVE_INJECTION.search(text):
        matched.append("sensitive_key_in_prompt")
        score += 1

    # Heuristic: very long prompt with many instructions-like sentences is suspicious
    if len(text) > 2000 and text.lower().count("instruction") > 3:
        score += 1
        matched.append("long_instruction_heavy")

    if score >= 6:
        risk = "critical"
        block = True
    elif score >= 3:
        risk = "high"
        block = True
    elif score >= 1:
        risk = "medium"
        block = False
    else:
        risk = "low"
        block = False

    return {"score": score, "matched": matched, "risk_level": risk, "should_block": block, "blocked": block}
