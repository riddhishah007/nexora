"""Unit tests for Planner._parse and provider-failure fallback."""

import pytest

from app.llm.schemas import LLMResponse
from app.orchestrator.planner import PLANNER_SYSTEM, PLAN_SCHEMA, Planner, PlannedStep


class FakeGateway:
    def __init__(self, text: str | None = None, raise_exc: Exception | None = None):
        self._text = text
        self._raise = raise_exc
        self.calls = 0

    async def generate(self, prompt, tier=None, system=None, response_schema=None):
        self.calls += 1
        if self._raise:
            raise self._raise
        return LLMResponse(
            text=self._text or "",
            provider="fake",
            model="fake-1",
            tokens_in=1,
            tokens_out=1,
            latency_ms=1,
            mock=True,
        )


GOOD_SINGLE = '{"steps": [{"agent_id": "search-agent", "instruction": "find it"}]}'
GOOD_MULTI = (
    '{"steps": ['
    '{"agent_id": "research-agent", "instruction": "research X", "depends_on": []},'
    '{"agent_id": "writer-agent", "instruction": "write report", "depends_on": [0]}'
    "]}"
)


def test_parse_single_step():
    steps = Planner._parse(GOOD_SINGLE)
    assert len(steps) == 1
    assert steps[0].agent_id == "search-agent"
    assert steps[0].depends_on == []


def test_parse_multi_with_deps():
    steps = Planner._parse(GOOD_MULTI)
    assert [s.agent_id for s in steps] == ["research-agent", "writer-agent"]
    assert steps[1].depends_on == [0]


def test_parse_unknown_agent_raises():
    with pytest.raises(ValueError):
        Planner._parse('{"steps": [{"agent_id": "nope", "instruction": "x"}]}')


def test_parse_forward_dependency_raises():
    bad = '{"steps": [{"agent_id": "search-agent", "instruction": "a", "depends_on": [1]}, {"agent_id": "search-agent", "instruction": "b"}]}'
    with pytest.raises(ValueError):
        Planner._parse(bad)


def test_parse_empty_plan_raises():
    with pytest.raises(ValueError):
        Planner._parse('{"steps": []}')


def test_parse_too_large_raises():
    import json

    big = json.dumps({"steps": [{"agent_id": "search-agent", "instruction": f"s{i}"} for i in range(9)]})
    with pytest.raises(ValueError):
        Planner._parse(big)


def test_parse_invalid_json_raises():
    with pytest.raises(Exception):
        Planner._parse("not json at all")


async def test_build_plan_happy_path():
    gw = FakeGateway(GOOD_MULTI)
    plan, llm = await Planner(gw).build_plan("research X and write a report")  # type: ignore[arg-type]
    assert len(plan) == 2
    assert llm.provider == "fake"


async def test_build_plan_provider_failure_falls_back():
    gw = FakeGateway(raise_exc=RuntimeError("groq down"))
    plan, llm = await Planner(gw).build_plan("what is the tallest building?")
    assert len(plan) == 1
    assert plan[0].agent_id == "search-agent"
    assert plan[0].instruction == "what is the tallest building?"
    assert isinstance(llm, LLMResponse) and llm.mock is True


async def test_build_plan_malformed_json_falls_back():
    gw = FakeGateway("I am not JSON")
    plan, _llm = await Planner(gw).build_plan("hello")
    assert len(plan) == 1 and plan[0].agent_id == "search-agent"


def test_plan_constants_shape():
    assert "JSON" in PLANNER_SYSTEM
    assert PLAN_SCHEMA["required"] == ["steps"]
