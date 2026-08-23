# ADR 0002 — pgvector for RAG Vector Storage

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

RAG requires storing embeddings (~768 dims, Gemini text-embedding-004) with strict
per-project tenant filtering, hybrid search, and citation-grade metadata. Candidates:
Pinecone (paid, vendor lock), Weaviate/Milvus (self-host ops burden), Qdrant
(excellent, second datastore to keep consistent), pgvector (Postgres extension).

## Decision

Use **pgvector** on PostgreSQL 16 with HNSW index. Vectors live next to ownership
metadata in one transactional database; hybrid search = pgvector cosine ∥ Postgres
FTS fused via Reciprocal Rank Fusion. Retrieval sits behind a `Retriever` interface
so Qdrant remains a drop-in upgrade if scale ever demands it.

## Consequences

+ Zero new infrastructure; transactional consistency between chunks and ownership;
  SQL metadata filtering free; adequate into millions of chunks
+ Tenant isolation enforced by the same repository layer as all other data
− Postgres tuning eventually needed at high scale (accepted; interface hedges)
