import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.document import STATUS_UPLOADED, Document
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])

# Phase 19: Data Agent needs CSV/Excel; keep PDF for RAG. Allowlist per §25.
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",  # some browsers send CSV as text/plain
}
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".txt"}
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]")
_CHUNK = 1024 * 1024


def _sanitize_filename(raw: str | None) -> str:
    name = Path(raw or "document.pdf").name.strip()
    name = _UNSAFE_CHARS.sub("_", name).strip("._") or "document.pdf"
    return name[:255]


async def _read_upload(file: UploadFile) -> bytes:
    max_bytes = settings.max_upload_size_mb * _CHUNK
    buffer = bytearray()
    while chunk := await file.read(_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {settings.max_upload_size_mb} MB limit",
            )
    return bytes(buffer)


def _storage_dir() -> Path:
    path = Path(settings.file_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


class DocumentInfo(BaseModel):
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    status: str


def _info(doc: Document) -> DocumentInfo:
    return DocumentInfo(
        id=str(doc.id),
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        page_count=doc.page_count,
        status=doc.status,
    )


@router.post("", response_model=DocumentInfo)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentInfo:
    """Blueprint §25: type allow-list + size cap + sanitized, randomized
    storage name outside any web-servable root.
    Phase 19 adds CSV/Excel for Data Agent.
    """
    ctype = (file.content_type or "").lower().split(";")[0].strip()
    safe_name = _sanitize_filename(file.filename)
    ext = Path(safe_name).suffix.lower()

    # allow if either content-type or extension is in allowlist (browsers vary)
    if ctype not in ALLOWED_CONTENT_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ctype or ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File extension must be one of {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    payload = await _read_upload(file)
    # PDF magic-byte check only for PDFs
    if ext == ".pdf" and not payload.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not look like a PDF",
        )
    # basic sanity for CSV: must contain a comma or newline
    if ext in {".csv", ".txt"} and len(payload) > 0 and b"," not in payload[:1024] and b"\n" not in payload[:1024]:
        # allow but note; some single-column CSVs have no comma
        pass

    stored_name = f"{uuid.uuid4().hex}{ext}"
    (_storage_dir() / stored_name).write_bytes(payload)
    # normalize content_type for storage
    _ext_to_ctype = {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
    }
    stored_ctype = ctype if ctype in ALLOWED_CONTENT_TYPES else _ext_to_ctype.get(ext, "application/octet-stream")

    doc = Document(
        user_id=current_user.id,
        original_filename=safe_name,
        stored_name=stored_name,
        content_type=stored_ctype,
        size_bytes=len(payload),
        status=STATUS_UPLOADED,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _info(doc)


@router.get("", response_model=list[DocumentInfo])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentInfo]:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return [_info(d) for d in result.scalars().all()]


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentInfo:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from None
    doc = await db.get(Document, doc_uuid)
    if doc is None or doc.user_id != current_user.id:
        # 404, not 403: never confirm another user's resource exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return _info(doc)
