"""Shared structural representation used by every extractor, so the chunker
(4.7) can work off one shape regardless of source format.
"""

from dataclasses import dataclass
from typing import Literal

BlockKind = Literal["title", "paragraph"]


@dataclass
class StructuredBlock:
    kind: BlockKind
    text: str
    section: str | None = None  # nearest enclosing title, for chunk metadata
