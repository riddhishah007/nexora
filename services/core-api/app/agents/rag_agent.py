import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools import ToolContext, ToolRegistry

RAG_SYSTEM = (
    "You are the Nexora RAG Agent. You answer the user's question using ONLY "
    "the numbered document chunks provided. Cite sources inline as [1], [2], "
    "etc., where the number is the chunk's list position. If the chunks do "
    "not contain the answer, say so plainly — do not hallucinate. Be concise: "
    "2-5 sentences plus an optional short bulleted list when helpful."
)


class RagAgent:
    """Blueprint §6 registry entry 'rag-agent' — retrieval-grounded answering.

    Flow: search_documents tool (pgvector, user-scoped §16) -> numbered chunk
    block -> LLM Gateway synthesis (flash tier §11). Permission is
    knowledge:read — a different trust boundary from file:read (§9).
    """

    agent_id = "rag-agent"
    permissions = ["knowledge:read"]

    def __init__(
        self,
        gateway: LLMGateway,
        registry: ToolRegistry | None = None,
        user_id: str | None = None,
    ):
        self._gateway = gateway
        self._tools = registry
        self._user_id = user_id

    @property
    def tools(self) -> ToolContext:
        return ToolContext(
            agent_id=self.agent_id,
            user_id=self._user_id,
            permissions=self.permissions,
        )

    async def run(
        self,
        query: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        top_k: int | None = None,
        document_id: str | None = None,
    ) -> tuple[str, list[dict], LLMResponse]:
        started = time.perf_counter()
        chunks: list[dict] = []

        if self._tools is not None and db is not None:
            ctx = ToolContext(
                agent_id=self.agent_id,
                user_id=user_id or self._user_id,
                permissions=self.permissions,
            )
            payload: dict = {"query": query}
            if top_k is not None:
                payload["top_k"] = top_k
            if document_id is not None:
                payload["document_id"] = document_id
            result = await self._tools.execute("search_documents", payload, ctx, db=db)
            if result.ok:
                chunks = (result.data or {}).get("results", []) or []

        if not chunks:
            text = (
                "No relevant chunks were found in your ingested documents for "
                "this query. Try rephrasing, or ingest more documents."
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
        for i, c in enumerate(chunks, start=1):
            snippet = c.get("content", "")[:900].replace("\n", " ")
            blocks.append(
                f"[{i}] document_id={c.get('document_id')} chunk#{c.get('chunk_index')} distance={c.get('distance', 0):.3f}\n{snippet}"
            )
        context = "\n\n".join(blocks)

        prompt = f"Question: {query}\n\nRetrieved chunks:\n{context}"
        llm = await self._gateway.generate(
            prompt=prompt,
            tier=ModelTier.FLASH,
            system=RAG_SYSTEM,
        )
        return llm.text, chunks, llm
