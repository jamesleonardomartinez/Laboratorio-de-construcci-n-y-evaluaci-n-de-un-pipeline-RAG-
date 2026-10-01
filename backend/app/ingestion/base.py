import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Modality = Literal["text", "image"]
SourceType = Literal[
    "pdf", "docx", "txt", "markdown", "xlsx", "csv", "html", "url", "repo", "image", "audio", "video"
]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class Chunk:
    """A single unit of content (text passage or image) ready for embedding.

    Mirrors the chunk metadata contract from specs/document-ingestion/spec.md
    (Requirement: Chunk Metadata).
    """

    project_id: str
    source_id: str
    source_type: SourceType
    modality: Modality
    chunk_id: str
    content_hash: str
    embedding_model: str
    content: str = ""  # text content, empty for image chunks
    title: str | None = None
    section: str | None = None
    asset_path: str | None = None  # populated for image chunks
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def new_chunk_id() -> str:
    return uuid.uuid4().hex


def make_text_chunk(
    *,
    project_id: str,
    source_id: str,
    source_type: SourceType,
    content: str,
    embedding_model: str,
    title: str | None = None,
    section: str | None = None,
    chunk_id: str | None = None,
) -> Chunk:
    return Chunk(
        project_id=project_id,
        source_id=source_id,
        source_type=source_type,
        modality="text",
        chunk_id=chunk_id or new_chunk_id(),
        content_hash=content_hash(content),
        embedding_model=embedding_model,
        content=content,
        title=title,
        section=section,
    )


def make_image_chunk(
    *,
    project_id: str,
    source_id: str,
    source_type: SourceType,
    asset_path: str,
    embedding_model: str,
    chunk_id: str | None = None,
) -> Chunk:
    # Image chunks hash the asset path + source_id, since pixel content is not
    # text; identical bytes re-ingested under the same source/chunk id are
    # treated as unchanged.
    return Chunk(
        project_id=project_id,
        source_id=source_id,
        source_type=source_type,
        modality="image",
        chunk_id=chunk_id or new_chunk_id(),
        content_hash=content_hash(f"{source_id}:{asset_path}"),
        embedding_model=embedding_model,
        asset_path=asset_path,
    )
