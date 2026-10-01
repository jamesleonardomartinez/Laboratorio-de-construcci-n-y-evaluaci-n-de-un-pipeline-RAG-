"""End-to-end ingestion wiring (4.9): source -> extract/clean -> chunk
(+ frame extraction for video) -> embed -> upsert.
"""

import asyncio
import logging

from app.config import settings
from app.db import repository
from app.embeddings.image import embed_images
from app.embeddings.ocr import extract_text_from_image
from app.embeddings.text import embed_texts
from app.ingestion.base import SourceType, content_hash, make_image_chunk, make_text_chunk
from app.ingestion.chunker import chunk_blocks
from app.ingestion.documents import extract_document
from app.ingestion.images import ocr_text_to_blocks, store_image_asset
from app.ingestion.media import extract_key_frames, transcribe_media, transcript_to_blocks
from app.ingestion.repos import extract_repo
from app.ingestion.structure import StructuredBlock
from app.ingestion.urls import extract_url

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {"pdf", "docx", "txt", "markdown", "xlsx", "csv", "html"}


async def run_ingestion(
    *,
    job_id: str,
    project_id: str,
    source_id: str,
    source_type: SourceType,
    path_or_url: str,
    title: str | None = None,
) -> None:
    try:
        chunk_count = await _ingest(
            project_id=project_id,
            source_id=source_id,
            source_type=source_type,
            path_or_url=path_or_url,
            title=title,
        )
        await repository.mark_job_completed(job_id, chunk_count)
        await repository.upsert_source(project_id, source_id, source_type, title, chunk_count)
    except Exception as exc:  # noqa: BLE001 - surfaced via job status, not re-raised
        logger.exception("Ingestion failed for job %s", job_id)
        await repository.mark_job_failed(job_id, str(exc))


async def _ingest(
    *, project_id: str, source_id: str, source_type: SourceType, path_or_url: str, title: str | None
) -> int:
    text_chunk_count = 0
    image_chunk_count = 0

    if source_type in DOCUMENT_TYPES:
        blocks = await asyncio.to_thread(extract_document, path_or_url)
        text_chunk_count += await _embed_and_store_text_blocks(
            project_id, source_id, source_type, blocks
        )

    elif source_type == "url":
        blocks = await asyncio.to_thread(extract_url, path_or_url)
        text_chunk_count += await _embed_and_store_text_blocks(
            project_id, source_id, source_type, blocks
        )

    elif source_type == "repo":
        files = await asyncio.to_thread(extract_repo, path_or_url)
        used_source_ids: list[str] = []
        for file_source_id, blocks in files.items():
            composite_id = f"{source_id}:{file_source_id}"
            text_chunk_count += await _embed_and_store_text_blocks(
                project_id, composite_id, source_type, blocks
            )
            used_source_ids.append(composite_id)
        # Remove chunks for files that were excluded/removed since the last ingest.
        await repository.delete_stale_repo_text_chunks(project_id, source_id, used_source_ids)

    elif source_type == "image":
        asset_path = await asyncio.to_thread(store_image_asset, path_or_url, project_id, source_id)
        image_chunk_count += await _embed_and_store_image_assets(
            project_id, source_id, source_type, [asset_path]
        )

        ocr_text = await asyncio.to_thread(extract_text_from_image, asset_path)
        blocks = ocr_text_to_blocks(ocr_text)
        text_chunk_count += await _embed_and_store_text_blocks(
            project_id, source_id, source_type, blocks
        )

    elif source_type == "audio":
        transcript = await asyncio.to_thread(transcribe_media, path_or_url)
        blocks = transcript_to_blocks(transcript)
        text_chunk_count += await _embed_and_store_text_blocks(
            project_id, source_id, source_type, blocks
        )

    elif source_type == "video":
        transcript = await asyncio.to_thread(transcribe_media, path_or_url)
        transcript_blocks = transcript_to_blocks(transcript)

        frame_paths = await asyncio.to_thread(
            extract_key_frames, path_or_url, project_id, source_id
        )
        image_chunk_count += await _embed_and_store_image_assets(
            project_id, source_id, source_type, frame_paths
        )

        # A silent/narration-free screen recording has no usable transcript, so
        # any on-screen text is only reachable by OCR-ing the sampled frames.
        # Combined into a single call so chunk_ids stay contiguous across both
        # sources and the stale-chunk cleanup below doesn't wipe one out from
        # under the other.
        frame_text_blocks = await asyncio.to_thread(_ocr_key_frames, frame_paths)
        text_chunk_count += await _embed_and_store_text_blocks(
            project_id, source_id, source_type, transcript_blocks + frame_text_blocks
        )

    else:
        raise ValueError(f"Unsupported source type: {source_type}")

    return text_chunk_count + image_chunk_count


def _ocr_key_frames(frame_paths: list[str]) -> list[StructuredBlock]:
    """OCRs each sampled key frame. Consecutive frames sampled a few seconds
    apart from the same screen tend to repeat the same on-screen text, so an
    unchanged reading is skipped rather than stored as a near-duplicate chunk."""
    blocks: list[StructuredBlock] = []
    last_text: str | None = None
    for frame_path in frame_paths:
        text = extract_text_from_image(frame_path)
        if not text or text == last_text:
            continue
        blocks.append(StructuredBlock(kind="paragraph", text=text))
        last_text = text
    return blocks


async def _embed_and_store_text_blocks(
    project_id: str, source_id: str, source_type: SourceType, blocks: list[StructuredBlock]
) -> int:
    chunk_texts = chunk_blocks(blocks)
    if not chunk_texts:
        await repository.delete_stale_text_chunks(project_id, source_id, [])
        return 0

    # Content-addressed, not positional: the chunk_id is a hash of its own
    # (section, text), so a paragraph keeps the same id even if earlier
    # content shifts its position in the chunk list. This is computed up
    # front, before touching the embedding model or the database.
    candidates = []
    for text, section in chunk_texts:
        section_key = section or ""
        chunk_id = f"text-{content_hash(f'{section_key}:{text}')}"
        candidates.append((chunk_id, text, section))
    all_chunk_ids = [chunk_id for chunk_id, _, _ in candidates]

    # A chunk_id that already exists for this source IS, by construction, the
    # same (section, text) already embedded and stored - re-embedding it would
    # produce the identical vector. Skip the model call entirely for those, so
    # editing 1 paragraph out of 500 costs 1 embedding call, not 500.
    existing_ids = await repository.get_existing_chunk_ids(project_id, source_id, all_chunk_ids)
    to_embed = [c for c in candidates if c[0] not in existing_ids]

    if to_embed:
        embeddings = await asyncio.to_thread(embed_texts, [text for _, text, _ in to_embed])
        for (chunk_id, text, section), embedding in zip(to_embed, embeddings):
            chunk = make_text_chunk(
                project_id=project_id,
                source_id=source_id,
                source_type=source_type,
                content=text,
                embedding_model=settings.text_embedding_model.rsplit("/", 1)[-1],
                title=section,
                section=section,
                chunk_id=chunk_id,
            )
            await repository.upsert_text_chunk(chunk, embedding)

    # Drop any chunks left over from a previous ingest that produced more.
    await repository.delete_stale_text_chunks(project_id, source_id, all_chunk_ids)
    return len(candidates)


async def _embed_and_store_image_assets(
    project_id: str, source_id: str, source_type: SourceType, asset_paths: list[str]
) -> int:
    if not asset_paths:
        await repository.delete_stale_image_chunks(project_id, source_id, [])
        return 0

    embeddings = await asyncio.to_thread(embed_images, asset_paths)

    stored = 0
    chunk_ids: list[str] = []
    for index, (asset_path, embedding) in enumerate(zip(asset_paths, embeddings)):
        chunk_id = f"image-{index:04d}"
        chunk = make_image_chunk(
            project_id=project_id,
            source_id=source_id,
            source_type=source_type,
            asset_path=asset_path,
            embedding_model=settings.image_embedding_model.rsplit("/", 1)[-1],
            chunk_id=chunk_id,
        )
        await repository.upsert_image_chunk(chunk, embedding, asset_path)
        chunk_ids.append(chunk_id)
        stored += 1

    await repository.delete_stale_image_chunks(project_id, source_id, chunk_ids)
    return stored
