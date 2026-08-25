import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools import ToolContext, ToolRegistry

RESEARCH_SYSTEM = (
    "You are the Nexora Research Agent. You are a senior researcher who breaks "
    "complex questions into sub-questions, searches for each, cross-checks sources "
    "for consistency, and synthesizes a cited report. For each sub-question, cite "
    "sources as [1], [2], etc. If sources conflict, note the conflict. Be thorough: "
    "3-5 sentences per sub-question plus a final synthesis. Always cite. "
    "Do not use <think> tags or show your reasoning — only the final report."
)

SYNTHESIS_SYSTEM = (
    "You are the Nexora Research Synthesizer. Combine the sub-question searches into "
    "one coherent, cited report. Structure: Executive Summary (2-3 sentences), "
    "Findings (bulleted sub-questions with citations), Cross-check (conflicts/limitations), "
    "Conclusion. Cite as [1], [2]. Do not use <think> tags."
)


class ResearchAgent:
    """Blueprint §5 V1 Research Agent — subquestions, cross-check, synthesis.

    Flow: LLM -> subquestions (via flash) -> search_web per subquestion (via
    ToolRegistry, network:read) -> synthesis (flash) with citations.
    """

    agent_id = "research-agent"
    permissions = ["network:read"]

    def __init__(self, gateway: LLMGateway, registry: ToolRegistry | None = None, user_id: str | None = None):
        self._gateway = gateway
        self._tools = registry
        self._user_id = user_id

    @property
    def tools(self) -> ToolContext:
        return ToolContext(agent_id=self.agent_id, user_id=self._user_id, permissions=self.permissions)

    async def run(
        self,
        task: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
    ) -> tuple[str, list[dict], LLMResponse]:
        started = time.perf_counter()
        # 1. generate subquestions via LLM (or fallback to task itself)
        subquestions: list[str] = []
        try:
            sq_prompt = f"Break this research task into 2-3 focused sub-questions, one per line, no numbering:\nTask: {task}"
            sq_llm = await self._gateway.generate(prompt=sq_prompt, tier=ModelTier.FLASH, system="You generate concise sub-questions.")
            # split by lines, filter
            for line in sq_llm.text.splitlines():
                q = line.strip().lstrip("0123456789.-• ").strip()
                if q and len(q) > 10:
                    subquestions.append(q)
                if len(subquestions) >= 3:
                    break
        except Exception:
            pass
        if not subquestions:
            subquestions = [task]

        # 2. search per subquestion via tool
        all_results: list[dict] = []
        ctx = ToolContext(agent_id=self.agent_id, user_id=user_id or self._user_id, permissions=self.permissions)
        for sq in subquestions[:3]:
            if self._tools is None:
                break
            result = await self._tools.execute("search_web", {"query": sq}, ctx, db=db)
            if result.ok:
                for r in (result.data or {}).get("results", [])[:2]:
                    if r.get("url"):
                        all_results.append({**r, "subquestion": sq})

        if not all_results:
            text = "No usable sources were returned for the research sub-questions. Try rephrasing."
            llm = LLMResponse(text=text, provider="none", model="n/a", tokens_in=0, tokens_out=0, latency_ms=int((time.perf_counter() - started) * 1000), mock=True)
            return text, [], llm

        # 3. synthesize with citations
        blocks = []
        for i, r in enumerate(all_results, start=1):
            snippet = r.get("content", "")[:700].replace("\n", " ")
            blocks.append(f"[{i}] {r.get('title','')} — {r.get('subquestion','')}\nURL: {r.get('url')}\n{snippet}")
        context = "\n\n".join(blocks)
        prompt = f"Research Task: {task}\nSub-questions: {'; '.join(subquestions)}\n\nSources:\n{context}\n\nProduce the research report."
        llm = await self._gateway.generate(prompt=prompt, tier=ModelTier.FLASH, system=SYNTHESIS_SYSTEM)
        # keep latency
        llm.latency_ms = int((time.perf_counter() - started) * 1000) if llm.latency_ms == 0 else llm.latency_ms
        return llm.text, all_results, llm
