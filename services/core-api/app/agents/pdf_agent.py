import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools import ToolContext, ToolRegistry

SUMMARIZE_SYSTEM = (
    "You are the Nexora PDF Agent. You summarize documents using ONLY "
    "the extracted text provided, which is marked by page like [Page 2]. "
    "Cite pages inline as [Page N]. Produce: a 3-5 sentence executive "
    "summary, then 3-6 key-point bullets. If the text is empty or "
    "unreadable, say so plainly."
)


class PdfAgent:
    """Blueprint §6 registry entry 'pdf-agent' — Upload -> parse -> summarize.

    Powers are exactly file:read on the caller's own uploads (§9); every
    read goes through the ToolRegistry with user-scoped isolation checks.
    """

    agent_id = "pdf-agent"
    permissions = ["file:read"]

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
        document_id: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
    ) -> tuple[str, dict, LLMResponse]:
        started = time.perf_counter()

        ctx = ToolContext(
            agent_id=self.agent_id,
            user_id=user_id or self._user_id,
            permissions=self.permissions,
        )
        result = await self._tools.execute(
            "extract_text", {"document_id": document_id}, ctx, db=db
        )
        meta = {
            "document_id": document_id,
            "page_count": None,
            "truncated": False,
            "chars": 0,
        }

        if not result.ok:
            llm = LLMResponse(
                text=f"Could not read that document: {result.error}",
                provider="none",
                model="n/a",
                tokens_in=0,
                tokens_out=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
                mock=True,
            )
            return llm.text, meta, llm

        data = result.data or {}
        meta.update(
            page_count=data.get("page_count"),
            truncated=data.get("truncated", False),
            chars=data.get("chars", 0),
        )
        text = data.get("text", "")
        if not text.strip():
            note = (
                "This PDF contains no extractable text (it may be "
                "scanned images). OCR is not part of the MVP."
            )
            llm = LLMResponse(
                text=note,
                provider="none",
                model="n/a",
                tokens_in=0,
                tokens_out=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
                mock=True,
            )
            return note, meta, llm

        trailer = (
            "\n\n(Note: the document was longer than the extraction cap; "
            "summary covers the beginning of the file.)"
            if meta["truncated"]
            else ""
        )
        prompt = f"Document '{data.get('filename', '')}':\n\n{text}{trailer}"
        llm = await self._gateway.generate(
            prompt=prompt,
            tier=ModelTier.FLASH,
            system=SUMMARIZE_SYSTEM,
        )
        return llm.text, meta, llm
