from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import ToolContext, ToolDefinition
from app.tools.pdf_io import document_path, load_owned_document, read_pdf_pages


class DocumentIdInput(BaseModel):
    document_id: str = Field(min_length=32, max_length=64)


def _validated_document_id(payload: dict[str, Any]) -> str:
    try:
        return DocumentIdInput.model_validate(payload).document_id
    except Exception:
        from app.tools.base import ToolExecutionError

        raise ToolExecutionError("document_id is required") from None


class ParsePdfTool:
    """Blueprint §8 tool: parse_pdf. Returns structural metadata plus a
    per-page character census so callers can size downstream prompts.
    Permission: file:read (§9 — own uploads only, enforced by pdf_io).
    """

    definition = ToolDefinition(
        tool_id="parse_pdf",
        name="Parse PDF",
        description="Parses one of the caller's uploaded PDFs and returns "
        "page count plus per-page text sizes.",
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "minLength": 32,
                    "maxLength": 64,
                }
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
        required_permission="file:read",
        trust_level="medium",
        timeout_seconds=30.0,
    )

    async def run(
        self,
        payload: dict[str, Any],
        ctx: ToolContext,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        document_id = _validated_document_id(payload)
        doc = await load_owned_document(db, ctx, document_id)
        page_count, pages = read_pdf_pages(document_path(doc))

        if db is not None:
            doc.page_count = page_count
            await db.commit()

        return {
            "document_id": document_id,
            "filename": doc.original_filename,
            "page_count": page_count,
            "pages": [
                {"page": i + 1, "chars": len(t)} for i, t in enumerate(pages)
            ],
            "mock": False,
        }
