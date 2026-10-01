"""Image source handling (4.4) — stored as an asset, no text-cleaning applied
to the image itself. `ocr_text_to_blocks` is a separate, optional path that
lets any text found *inside* the image (e.g. a screenshot) flow through the
normal text search, since SigLIP's visual embedding alone does not reliably
surface text-heavy images for a text question."""

import shutil
from pathlib import Path

from app.config import settings
from app.ingestion.structure import StructuredBlock


def store_image_asset(source_path: str, project_id: str, source_id: str) -> str:
    """Copies the image into the project's asset directory and returns the stored path."""
    dest_dir = Path(settings.upload_dir) / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{source_id}{Path(source_path).suffix}"
    shutil.copy2(source_path, dest_path)
    return str(dest_path)


def ocr_text_to_blocks(text: str) -> list[StructuredBlock]:
    """OCR output has no heading structure, so it is chunked as an
    unstructured paragraph block (same fallback path as a plain-text file)."""
    return [StructuredBlock(kind="paragraph", text=text)] if text else []
