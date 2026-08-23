from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.tools.base import ToolContext, ToolDefinition
from app.tools.pdf_io import document_path, load_owned_document, read_pdf_pages
from app.tools.parse_pdf import _validated_document_id


class ExtractTextTool:
    """Blueprint §8 tool: extract_text. Returns the PDF's text (capped at
    PDF_EXTRACT_MAX_CHARS) with page markers, ready for an LLM prompt.
    Permission: file:read — same isolation as parse_pdf.
    """

    definition = ToolDefinition(
        tool_id="extract_text",
        name="Extract Text",
        description="Extracts the full text of one of the caller's uploaded "
        "PDFs, with [Page N] markers, truncated to a size cap.",
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

        parts: list[str] = []
        total = 0
        truncated = False
        for i, text in enumerate(pages, start=1):
            clean = text.strip()
            if not clean:
                continue
            block = f"[Page {i}]\n{clean}"
            if total + len(block) > settings.pdf_extract_max_chars:
                remaining = settings.pdf_extract_max_chars - total
                if remaining > 0:
                    parts.append(block[:remaining])
                    total += remaining
                truncated = True
                break
            parts.append(block)
            total += len(block)

        return {
            "document_id": document_id,
            "filename": doc.original_filename,
            "page_count": page_count,
            "chars": total,
            "truncated": truncated,
            "text": "\n\n".join(parts),
            "mock": False,
        }
