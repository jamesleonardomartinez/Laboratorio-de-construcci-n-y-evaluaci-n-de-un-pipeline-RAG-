import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.connection import get_pool
from app.ingestion.base import Chunk

# --- Upsert (2.5) ---------------------------------------------------------
# INSERT ... ON CONFLICT (project_id, source_id, chunk_id) DO UPDATE ...
# WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash
#
# This inserts a brand-new row, updates the row if content changed, and is a
# no-op (no re-embedding cost paid) if the content hash is unchanged.

_TEXT_UPSERT_SQL = """
INSERT INTO text_chunks (
    project_id, source_id, chunk_id, content_hash, source_type,
    title, section, content, embedding_model, embedding
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (project_id, source_id, chunk_id)
DO UPDATE SET
    content_hash = EXCLUDED.content_hash,
    source_type = EXCLUDED.source_type,
    title = EXCLUDED.title,
    section = EXCLUDED.section,
    content = EXCLUDED.content,
    embedding_model = EXCLUDED.embedding_model,
    embedding = EXCLUDED.embedding,
    updated_at = now()
WHERE text_chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash
RETURNING (xmax = 0) AS inserted;
"""

_IMAGE_UPSERT_SQL = """
INSERT INTO image_chunks (
    project_id, source_id, chunk_id, content_hash, source_type,
    asset_path, embedding_model, embedding
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (project_id, source_id, chunk_id)
DO UPDATE SET
    content_hash = EXCLUDED.content_hash,
    source_type = EXCLUDED.source_type,
    asset_path = EXCLUDED.asset_path,
    embedding_model = EXCLUDED.embedding_model,
    embedding = EXCLUDED.embedding,
    updated_at = now()
WHERE image_chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash
RETURNING (xmax = 0) AS inserted;
"""


async def get_existing_chunk_ids(
    project_id: str, source_id: str, candidate_ids: list[str]
) -> set[str]:
    """Of these candidate chunk_ids (hashes of section+text), which already
    exist for this source? Since the id IS a hash of the content, existing =
    identical content already stored - the caller uses this to skip paying
    the embedding-model cost for chunks that haven't actually changed."""
    if not candidate_ids:
        return set()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_id FROM text_chunks
            WHERE project_id = $1 AND source_id = $2 AND chunk_id = ANY($3::text[]);
            """,
            project_id,
            source_id,
            candidate_ids,
        )
        return {r["chunk_id"] for r in rows}


async def upsert_text_chunk(chunk: Chunk, embedding: list[float]) -> bool:
    """Returns True if the row was newly created or updated, False if skipped (unchanged hash)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _TEXT_UPSERT_SQL,
            chunk.project_id,
            chunk.source_id,
            chunk.chunk_id,
            chunk.content_hash,
            chunk.source_type,
            chunk.title,
            chunk.section,
            chunk.content,
            chunk.embedding_model,
            embedding,
        )
        return row is not None


async def upsert_image_chunk(chunk: Chunk, embedding: list[float], asset_path: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _IMAGE_UPSERT_SQL,
            chunk.project_id,
            chunk.source_id,
            chunk.chunk_id,
            chunk.content_hash,
            chunk.source_type,
            asset_path,
            chunk.embedding_model,
            embedding,
        )
        return row is not None


async def delete_stale_text_chunks(
    project_id: str, source_id: str, keep_chunk_ids: list[str]
) -> None:
    """Removes chunks for a source that are no longer produced by extraction
    (e.g. after a re-ingest yields fewer chunks), so stale content cannot keep
    surfacing in retrieval."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM text_chunks
            WHERE project_id = $1 AND source_id = $2 AND chunk_id <> ALL($3::text[]);
            """,
            project_id,
            source_id,
            keep_chunk_ids,
        )


async def delete_stale_image_chunks(
    project_id: str, source_id: str, keep_chunk_ids: list[str]
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM image_chunks
            WHERE project_id = $1 AND source_id = $2 AND chunk_id <> ALL($3::text[]);
            """,
            project_id,
            source_id,
            keep_chunk_ids,
        )


async def delete_stale_repo_text_chunks(
    project_id: str, base_source_id: str, keep_source_ids: list[str]
) -> None:
    """Drops chunks of repo files that no longer exist (their source_id is
    `<base_source_id>:<file>`), so removed/excluded files leave nothing behind."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM text_chunks
            WHERE project_id = $1
              AND source_id LIKE $2 || ':%'
              AND source_id <> ALL($3::text[]);
            """,
            project_id,
            base_source_id,
            keep_source_ids,
        )


# --- Similarity search (2.6) ----------------------------------------------

@dataclass
class TextSearchResult:
    source_id: str
    chunk_id: str
    source_type: str
    title: str | None
    section: str | None
    content: str
    similarity: float


async def search_text_chunks(
    project_id: str, query_embedding: list[float], limit: int = 5
) -> list[TextSearchResult]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source_id, chunk_id, source_type, title, section, content,
                   1 - (embedding <=> $2) AS similarity
            FROM text_chunks
            WHERE project_id = $1
            ORDER BY embedding <=> $2
            LIMIT $3;
            """,
            project_id,
            query_embedding,
            limit,
        )
        return [
            TextSearchResult(
                source_id=r["source_id"],
                chunk_id=r["chunk_id"],
                source_type=r["source_type"],
                title=r["title"],
                section=r["section"],
                content=r["content"],
                similarity=r["similarity"],
            )
            for r in rows
        ]


@dataclass
class ImageSearchResult:
    source_id: str
    chunk_id: str
    asset_path: str
    similarity: float


async def search_image_chunks(
    project_id: str, query_embedding: list[float], limit: int = 5
) -> list[ImageSearchResult]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source_id, chunk_id, asset_path,
                   1 - (embedding <=> $2) AS similarity
            FROM image_chunks
            WHERE project_id = $1
            ORDER BY embedding <=> $2
            LIMIT $3;
            """,
            project_id,
            query_embedding,
            limit,
        )
        return [
            ImageSearchResult(
                source_id=r["source_id"],
                chunk_id=r["chunk_id"],
                asset_path=r["asset_path"],
                similarity=r["similarity"],
            )
            for r in rows
        ]


# --- Ingestion jobs ---------------------------------------------------------

async def create_ingestion_job(
    project_id: str, source_id: str, source_type: str, original_name: str | None
) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """
            INSERT INTO ingestion_jobs (project_id, source_id, source_type, original_name, status)
            VALUES ($1, $2, $3, $4, 'processing')
            RETURNING id;
            """,
            project_id,
            source_id,
            source_type,
            original_name,
        )
        return str(job_id)


async def mark_job_completed(job_id: str, chunk_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'completed', chunk_count = $2, updated_at = now()
            WHERE id = $1;
            """,
            uuid.UUID(job_id),
            chunk_count,
        )


async def mark_job_failed(job_id: str, error: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'failed', error = $2, updated_at = now()
            WHERE id = $1;
            """,
            uuid.UUID(job_id),
            error,
        )


async def get_job_status(project_id: str, job_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, project_id, source_id, source_type, original_name,
                   status, chunk_count, error, created_at, updated_at
            FROM ingestion_jobs
            WHERE id = $1 AND project_id = $2;
            """,
            uuid.UUID(job_id),
            project_id,
        )
        return dict(row) if row else None


# --- Sources -----------------------------------------------------------------

async def upsert_source(
    project_id: str, source_id: str, source_type: str, title: str | None, chunk_count: int
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sources (project_id, source_id, source_type, title, chunk_count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (project_id, source_id)
            DO UPDATE SET
                source_type = EXCLUDED.source_type,
                title = EXCLUDED.title,
                chunk_count = EXCLUDED.chunk_count,
                updated_at = now();
            """,
            project_id,
            source_id,
            source_type,
            title,
            chunk_count,
        )


async def list_sources(project_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source_id, source_type, title, chunk_count, created_at, updated_at
            FROM sources
            WHERE project_id = $1
            ORDER BY created_at DESC;
            """,
            project_id,
        )
        return [dict(r) for r in rows]


async def delete_source(project_id: str, source_id: str) -> None:
    """Removes a source and all its chunks (including repo file variants, whose
    chunk source_id is `<source_id>:<file>`)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM text_chunks
                WHERE project_id = $1
                  AND (source_id = $2 OR source_id LIKE $2 || ':%');
                """,
                project_id,
                source_id,
            )
            await conn.execute(
                """
                DELETE FROM image_chunks
                WHERE project_id = $1
                  AND (source_id = $2 OR source_id LIKE $2 || ':%');
                """,
                project_id,
                source_id,
            )
            await conn.execute(
                "DELETE FROM sources WHERE project_id = $1 AND source_id = $2;",
                project_id,
                source_id,
            )
