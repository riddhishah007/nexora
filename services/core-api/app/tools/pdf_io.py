"""Shared loader for file-reading tools (blueprint §9: the PDF Agent may
read only files its user uploaded). Every PDF tool must resolve documents
through here — ownership is re-checked in code, never trusted from input.
"""

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document
from app.tools.base import ToolContext, ToolError


async def load_owned_document(
    db: AsyncSession, ctx: ToolContext, document_id: str
) -> Document:
    if db is None:
        raise ToolError("tool requires a database session")
    if not ctx.user_id:
        raise ToolError("caller context has no user; refusing file access")

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise ToolError(f"invalid document id '{document_id}'") from None

    doc = await db.get(Document, doc_uuid)
    # Isolation boundary (§16): a document owned by anyone else is
    # indistinguishable from one that does not exist.
    if doc is None or str(doc.user_id) != ctx.user_id:
        # Phase 17: log potential isolation probe (exists but wrong owner)
        if doc is not None and db is not None:
            try:
                from app.security.events import log_security_event

                await log_security_event(
                    db,
                    event_type="data_isolation_violation",
                    risk_level="high",
                    blocked=True,
                    user_id=ctx.user_id,
                    details={"document_id": document_id, "owner": str(doc.user_id)},
                )
            except Exception:
                pass
        raise ToolError("document not found")

    path = Path(settings.file_storage_path) / doc.stored_name
    if not path.is_file():
        raise ToolError("document file missing from storage")
    return doc


def document_path(doc: Document) -> Path:
    return Path(settings.file_storage_path) / doc.stored_name


def read_pdf_pages(path: Path) -> tuple[int, list[str]]:
    """Extract per-page text with pypdf. Returns (page_count, page_texts).
    Raises ToolError for encrypted/corrupt files.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ToolError("PDF is encrypted and cannot be parsed")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except PdfReadError as exc:
        raise ToolError(f"unreadable PDF: {type(exc).__name__}") from None

    return len(pages), pages
