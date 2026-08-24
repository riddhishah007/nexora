"""Blueprint §13: semantic chunking (≈500-800 tokens, 10-15% overlap).

We chunk on characters (cheap, no extra tokenizer dep). 800 chars ~ ~200
tokens; overlap preserves boundary context. This is good enough for MVP
and mirrors text-embedding-004's max handling without tiktoken.
"""

from app.config import settings


def chunk_text(text: str, *, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into overlapping chunks.

    - Trims whitespace.
    - Falls back to settings rag_chunk_size/overlap.
    - Returns [] for empty input.
    """
    if chunk_size is None:
        chunk_size = settings.rag_chunk_size
    if overlap is None:
        overlap = settings.rag_chunk_overlap

    text = text.strip()
    if not text:
        return []

    # Defensive: overlap must be < chunk_size
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        piece = text[start: start + chunk_size]
        if not piece.strip():
            continue
        chunks.append(piece)
        # Stop exactly at end — avoid empty trailing chunk
        if start + chunk_size >= len(text):
            break
    return chunks
