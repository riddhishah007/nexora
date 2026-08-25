import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier

WRITER_SYSTEM = (
    "You are the Nexora Writer Agent. You are a senior technical writer who produces "
    "polished, structured reports. Given a task and optional context (research findings, "
    "data analysis, citations), generate a markdown report with: Title, Executive Summary "
    "(3-4 sentences), Main Body (with headings, bullets, and inline citations like [1]), "
    "Key Takeaways (3-5 bullets), and References. Use clear, professional tone. "
    "If context includes citations, preserve them. If no context, state that."
)


class WriterAgent:
    """Blueprint §5 V1 Writer/Report Agent — style/brand-tuned generation.

    Flow: LLM (flash) with writer system prompt, no tools for MVP. Future: file:write
    to generate PDF via reportlab, brand templates, etc.
    """

    agent_id = "writer-agent"
    permissions: list[str] = []  # LLM-only for MVP, no tool needed

    def __init__(self, gateway: LLMGateway, registry=None, user_id: str | None = None):
        self._gateway = gateway
        self._tools = registry
        self._user_id = user_id

    async def run(
        self,
        task: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        context: str | None = None,
    ) -> tuple[str, dict, LLMResponse]:
        started = time.perf_counter()
        prompt = f"Task: {task}"
        if context:
            prompt += f"\n\nContext (previous agent outputs, cite if present):\n{context[:4000]}"
        llm = await self._gateway.generate(prompt=prompt, tier=ModelTier.FLASH, system=WRITER_SYSTEM)
        llm.latency_ms = int((time.perf_counter() - started) * 1000) if llm.latency_ms == 0 else llm.latency_ms
        meta = {"context_chars": len(context) if context else 0}
        return llm.text, meta, llm
