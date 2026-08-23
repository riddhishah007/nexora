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

ALLOWED_CONTENT_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}
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
    """
    if (file.content_type or "").lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported in MVP",
        )

    safe_name = _sanitize_filename(file.filename)
    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File extension must be .pdf",
        )

    payload = await _read_upload(file)
    if not payload.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not look like a PDF",
        )

    stored_name = f"{uuid.uuid4().hex}.pdf"
    (_storage_dir() / stored_name).write_bytes(payload)

    doc = Document(
        user_id=current_user.id,
        original_filename=safe_name,
        stored_name=stored_name,
        content_type="application/pdf",
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
