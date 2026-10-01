"""PDF / DOCX / XLSX / CSV / TXT / Markdown extraction and boilerplate filtering (4.1)."""

import re
from collections import Counter

from unstructured.partition.auto import partition

from app.ingestion.structure import StructuredBlock

_BOILERPLATE_CATEGORIES = {"Header", "Footer", "PageBreak", "PageNumber"}

# A line repeated on 3+ pages is treated as a running header/footer even if
# the extractor didn't tag it as one (common for PDFs exported without
# semantic header/footer markup).
_REPEAT_THRESHOLD = 3

# The "fast" PDF extractor tags many short standalone lines — including full
# sentences that happen to sit on their own line — as titles. Treat an element
# as a real section heading only when it is short and does not read like a
# sentence, so a heading never gets separated from the body it labels.
_HEADING_MAX_CHARS = 60

# Plain PDFs with no distinct heading font/size (numbered sections like
# "2. Horario Laboral") get tagged as body text by unstructured's category
# classifier, not "Title" - without this, the whole document collapses into
# one running chunk since nothing ever triggers a section break.
_NUMBERED_HEADING_RE = re.compile(r"^\d+\.\s+\S")


def _is_heading(el) -> bool:
    text = el.text.strip()
    if len(text) > _HEADING_MAX_CHARS or text.endswith((".", ";", "!")):
        return False
    return el.category == "Title" or bool(_NUMBERED_HEADING_RE.match(text))


def extract_document(path: str) -> list[StructuredBlock]:
    elements = partition(filename=path)

    # First pass: drop explicitly-tagged boilerplate categories.
    candidates = [el for el in elements if el.category not in _BOILERPLATE_CATEGORIES]

    # Second pass: drop short lines repeated across many pages (running
    # headers/footers/logos the extractor didn't explicitly tag).
    text_counts = Counter(el.text.strip() for el in candidates if len(el.text.strip()) < 120)
    repeated = {text for text, count in text_counts.items() if count >= _REPEAT_THRESHOLD}

    blocks: list[StructuredBlock] = []
    current_section: str | None = None
    for el in candidates:
        text = el.text.strip()
        if not text or text in repeated:
            continue
        if _is_heading(el):
            current_section = text
            blocks.append(StructuredBlock(kind="title", text=text, section=current_section))
        else:
            blocks.append(StructuredBlock(kind="paragraph", text=text, section=current_section))

    return blocks
