"""OCR wrapper: extracts on-image text so image sources whose relevant
content is text (e.g. a screenshot) are also retrievable through the
existing text search, not just through SigLIP's visual similarity."""

from functools import lru_cache

import easyocr

_LANGUAGES = ["es", "en"]


@lru_cache(maxsize=1)
def _get_reader() -> easyocr.Reader:
    return easyocr.Reader(_LANGUAGES, gpu=False)


def extract_text_from_image(image_path: str) -> str:
    reader = _get_reader()
    lines = reader.readtext(image_path, detail=0, paragraph=True)
    return "\n".join(line.strip() for line in lines if line.strip())
