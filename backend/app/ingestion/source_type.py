"""Maps an upload (filename/url/explicit hint) to a supported SourceType, or
raises for anything unsupported (Requirement: Multi-Format Source Intake,
Scenario: Unsupported source type rejected)."""

from pathlib import Path

from app.ingestion.base import SourceType

_DOCUMENT_EXT = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".html": "html",
    ".htm": "html",
}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

_VALID_EXPLICIT: set[SourceType] = {
    "pdf", "docx", "txt", "markdown", "xlsx", "csv", "html", "url", "repo", "image", "audio", "video",
}


class UnsupportedSourceTypeError(ValueError):
    pass


def infer_source_type(
    *, filename: str | None, url: str | None, explicit: str | None
) -> SourceType:
    if explicit:
        if explicit not in _VALID_EXPLICIT:
            raise UnsupportedSourceTypeError(f"Unsupported source type: {explicit}")
        return explicit  # type: ignore[return-value]

    if filename:
        ext = Path(filename).suffix.lower()
        if ext in _DOCUMENT_EXT:
            return _DOCUMENT_EXT[ext]  # type: ignore[return-value]
        if ext in _IMAGE_EXT:
            return "image"
        if ext in _AUDIO_EXT:
            return "audio"
        if ext in _VIDEO_EXT:
            return "video"
        raise UnsupportedSourceTypeError(f"Unsupported file extension: {ext or '(none)'}")

    if url:
        return "url"

    raise UnsupportedSourceTypeError("No file, url, or explicit source_type provided")
