"""Blueprint §8 tool: search_documents (§13 retrieval, §16 isolation).

Wraps rag.service.retrieve with ToolRegistry security plumbing.
Permission: knowledge:read — scoped to the caller's own chunks.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import get_llm_gateway
from app.rag.service import retrieve
from app.tools.base import ToolContext, ToolDefinition


class SearchDocumentsTool:
    """Vector retrieval over the caller's own ingested PDFs."""

    definition = ToolDefinition(
        tool_id="search_documents",
        name="Search Documents",
        description=(
            "Retrieves the most relevant chunks from the caller's own "
            "ingested PDFs (pgvector cosine similarity, per-user isolation). "
            "Use for any question grounded in uploaded documents."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 4000},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                "document_id": {
                    "type": "string",
                    "minLength": 32,
                    "maxLength": 64,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        required_permission="knowledge:read",
        trust_level="medium",
        timeout_seconds=30.0,
    )

    async def run(
        self,
        payload: dict[str, Any],
        ctx: ToolContext,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        if db is None:
            raise RuntimeError("database session required")
        if not ctx.user_id:
            raise RuntimeError("caller context has no user; refusing vector access")

        query: str = payload["query"]
        top_k: int | None = payload.get("top_k")
        document_id: str | None = payload.get("document_id")

        gateway = get_llm_gateway()
        results = await retrieve(
            query=query,
            db=db,
            gateway=gateway,
            user_id=ctx.user_id,
            top_k=top_k,
            document_id=document_id,
        )
        return {"query": query, "results": results, "count": len(results)}
