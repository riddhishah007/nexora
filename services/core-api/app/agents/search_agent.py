import time

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools.search_web import SearchWebTool

SYNTHESIS_SYSTEM = (
    "You are the Nexora Search Agent. You answer user queries using ONLY "
    "the numbered web sources provided. Cite sources inline as [1], [2], "
    "etc. If the sources do not contain the answer, say so plainly. Be "
    "concise: 2-4 sentences plus a short source-backed list if helpful."
)


class SearchAgent:
    """Blueprint §6 registry entry 'search-agent' — MVP's first real agent.

    Flow: search_web tool (§8) -> numbered source block -> LLM Gateway
    synthesis (flash tier, §11). The agent holds no provider keys and has
    no other capabilities (§9: network:read only).
    """

    agent_id = "search-agent"

    def __init__(self, gateway: LLMGateway, search_tool: SearchWebTool | None = None):
        self._gateway = gateway
        self._search = search_tool or SearchWebTool()

    async def run(self, query: str) -> tuple[str, list[dict], LLMResponse]:
        started = time.perf_counter()
        results = await self._search.search(query)

        if not results:
            text = (
                "No usable sources were returned for this query. Try "
                "rephrasing it."
            )
            llm = LLMResponse(
                text=text,
                provider="none",
                model="n/a",
                tokens_in=0,
                tokens_out=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
                mock=True,
            )
            return text, [], llm

        blocks = []
        for i, r in enumerate(results, start=1):
            snippet = r["content"][:800].replace("\n", " ")
            blocks.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{snippet}")
        context = "\n\n".join(blocks)

        prompt = f"Query: {query}\n\nWeb sources:\n{context}"
        llm = await self._gateway.generate(
            prompt=prompt,
            tier=ModelTier.FLASH,
            system=SYNTHESIS_SYSTEM,
        )
        return llm.text, results, llm
