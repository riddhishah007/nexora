-- Run this in Supabase SQL Editor after creating your project
-- Enables pgvector for RAG embeddings (768-d text-embedding-004)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
