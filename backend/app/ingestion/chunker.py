"""Hierarchical/structure-aware chunking with fallback (4.7).

Groups structured blocks under their nearest title so a chunk never splits a
heading from its immediately following paragraph. When no titles are present
at all (e.g. a plain .txt file), falls back to fixed-size paragraph grouping.

Individual blocks that are larger than MAX_CHUNK_CHARS (a whole source file, a
spreadsheet sheet, a big table) are split into several pieces, preferring
blank-line, line, sentence, then word boundaries.
"""

from app.ingestion.structure import StructuredBlock

MAX_CHUNK_CHARS = 2000
FALLBACK_GROUP_SIZE = 3  # paragraphs per chunk when no structure is detected


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Splits a single long block into pieces of at most max_chars, cutting on the
    most natural boundary available (blank line > line > sentence > word)."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = -1
        for sep in ("\n\n", "\n", ". ", " "):
            idx = window.rfind(sep)
            # Only cut on a boundary that keeps the piece reasonably full.
            if idx >= max_chars // 2:
                cut = idx + len(sep)
                break
        if cut <= 0:
            cut = max_chars

        piece = remaining[:cut].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[cut:].lstrip()

    if remaining:
        pieces.append(remaining)
    return pieces


def chunk_blocks(blocks: list[StructuredBlock]) -> list[tuple[str, str | None]]:
    """Returns a list of (chunk_text, section) tuples."""
    if not blocks:
        return []

    has_structure = any(b.kind == "title" for b in blocks)
    if has_structure:
        return _chunk_by_structure(blocks)
    return _chunk_by_fallback(blocks)


def _chunk_by_structure(blocks: list[StructuredBlock]) -> list[tuple[str, str | None]]:
    chunks: list[tuple[str, str | None]] = []
    pending_headings: list[str] = []
    body_parts: list[str] = []
    section_title: str | None = None

    def flush(keep_headings: bool = False) -> None:
        nonlocal pending_headings, body_parts
        if not pending_headings and not body_parts:
            return
        chunks.append(("\n\n".join(pending_headings + body_parts), section_title))
        # A continuation chunk keeps the heading so it stays self-contained and
        # retrievable; the headings themselves are never emitted on their own.
        pending_headings = list(pending_headings) if keep_headings else []
        body_parts = []

    def add_body(text: str) -> None:
        for atom in _split_long_text(text, MAX_CHUNK_CHARS):
            if body_parts:
                candidate_len = (
                    sum(len(p) for p in pending_headings + body_parts) + len(atom)
                )
                if candidate_len > MAX_CHUNK_CHARS:
                    flush(keep_headings=True)
            body_parts.append(atom)

    for block in blocks:
        if block.kind == "title":
            # Only start a new section once the previous one has actual body,
            # so a heading immediately followed by another heading (e.g. the
            # document title followed by "Introducción") is not lost.
            if body_parts:
                flush()
            pending_headings.append(block.text)
            section_title = block.text
            continue

        add_body(block.text)

    flush()
    return chunks


def _chunk_by_fallback(blocks: list[StructuredBlock]) -> list[tuple[str, str | None]]:
    chunks: list[tuple[str, str | None]] = []
    for i in range(0, len(blocks), FALLBACK_GROUP_SIZE):
        group = blocks[i : i + FALLBACK_GROUP_SIZE]
        text = "\n\n".join(b.text for b in group)
        section = group[0].section
        for piece in _split_long_text(text, MAX_CHUNK_CHARS):
            chunks.append((piece, section))
    return chunks
