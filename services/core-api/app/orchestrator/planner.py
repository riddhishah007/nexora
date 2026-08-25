import json
import uuid

from app.agents import REGISTRY_INFO
from app.llm.gateway import LLMGateway
from app.llm.schemas import ModelTier

PLANNER_SYSTEM = (
    "You are the Nexora Orchestrator planner. Decompose the user's request "
    "into the smallest number of steps that answers it. Available agents "
    "and their supported tasks are given in the prompt. Respond with JSON "
    'matching exactly: {"steps": [{"agent_id": str, "instruction": str, '
    '"depends_on": [step indexes, 0-based, earlier steps only]}]}. '
    "Prefer a single step when one agent suffices."
)

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "instruction": {"type": "string"},
                    "depends_on": {
                        "type": "array", "items": {"type": "integer"}
                    },
                },
                "required": ["agent_id", "instruction"],
            },
        }
    },
    "required": ["steps"],
}


class PlannedStep:
    __slots__ = ("agent_id", "instruction", "depends_on")

    def __init__(self, agent_id: str, instruction: str, depends_on: list[int]):
        self.agent_id = agent_id
        self.instruction = instruction
        self.depends_on = depends_on


class PlanValidationError(Exception):
    pass


class Planner:
    """Blueprint §4: turns a chat message into a DAG of agent steps.

    Uses the LLM Gateway with structured output. If the model's plan is
    unusable (mock provider in dev, malformed JSON), falls back to a valid
    single-step search plan so the pipeline never dead-ends.
    """

    def __init__(self, gateway: LLMGateway):
        self._gateway = gateway

    async def build_plan(self, message: str) -> tuple[list[PlannedStep], object]:
        catalog = "\n".join(
            f"- {a.agent_id}: tasks={a.supported_tasks}"
            for a in REGISTRY_INFO
        )
        prompt = (
            f"Available agents:\n{catalog}\n\nUser request: {message}"
        )
        try:
            llm = await self._gateway.generate(
                prompt=prompt,
                tier=ModelTier.FLASH,
                system=PLANNER_SYSTEM,
                response_schema=PLAN_SCHEMA,
            )
        except Exception:
            # Provider outage/transient 4xx/5xx must not kill /chat — fall back
            # to a valid single-step plan so the pipeline never dead-ends.
            from app.llm.schemas import LLMResponse

            return (
                [PlannedStep(agent_id="search-agent", instruction=message, depends_on=[])],
                LLMResponse(text="", provider="none", model="n/a", tokens_in=0, tokens_out=0, latency_ms=0, mock=True),
            )
        try:
            return self._parse(llm.text), llm
        except (ValueError, KeyError, TypeError):
            fallback = [
                PlannedStep(
                    agent_id="search-agent",
                    instruction=message,
                    depends_on=[],
                )
            ]
            return fallback, llm

    @staticmethod
    def _parse(text: str) -> list[PlannedStep]:
        data = json.loads(text)
        raw_steps = data["steps"]
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("empty plan")

        known = {a.agent_id for a in REGISTRY_INFO}
        steps: list[PlannedStep] = []
        for i, s in enumerate(raw_steps):
            agent_id = str(s.get("agent_id", "")).strip()
            instruction = str(s.get("instruction", "")).strip()
            if not agent_id or not instruction:
                raise ValueError("step missing fields")
            if agent_id not in known:
                raise ValueError(f"unknown agent '{agent_id}'")
            deps_raw = s.get("depends_on", []) or []
            deps: list[int] = []
            for d in deps_raw:
                d = int(d)
                if d < 0 or d >= i:
                    raise ValueError("dependency must reference an earlier step")
                if d not in deps:
                    deps.append(d)
            steps.append(PlannedStep(agent_id, instruction, deps))
        if len(steps) > 8:
            raise ValueError("plan too large")
        return steps


def workflow_name(message: str) -> str:
    return message.strip()[:80] or f"workflow-{uuid.uuid4().hex[:8]}"
