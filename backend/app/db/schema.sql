-- 2.1 Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- 2.2 Text chunks (bge-m3, 1024-dim)
CREATE TABLE IF NOT EXISTS text_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT,
    section TEXT,
    content TEXT NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'bge-m3',
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, source_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS text_chunks_project_id_idx ON text_chunks (project_id);
CREATE INDEX IF NOT EXISTS text_chunks_embedding_hnsw_idx
    ON text_chunks USING hnsw (embedding vector_cosine_ops);

-- 2.3 Image chunks (siglip2-base-patch16, 768-dim)
CREATE TABLE IF NOT EXISTS image_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    asset_path TEXT NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'siglip2-base-patch16',
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, source_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS image_chunks_project_id_idx ON image_chunks (project_id);
CREATE INDEX IF NOT EXISTS image_chunks_embedding_hnsw_idx
    ON image_chunks USING hnsw (embedding vector_cosine_ops);

-- Ingestion jobs (upload -> status tracking)
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    original_name TEXT,
    status TEXT NOT NULL DEFAULT 'processing', -- processing | completed | failed
    chunk_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_jobs_project_id_idx ON ingestion_jobs (project_id);

-- Indexed sources (one row per successfully-ingested source, for the sources listing endpoint)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, source_id)
);

CREATE INDEX IF NOT EXISTS sources_project_id_idx ON sources (project_id);
