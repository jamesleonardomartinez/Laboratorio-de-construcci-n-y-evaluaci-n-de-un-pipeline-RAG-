"""URL extraction via trafilatura (4.2) — keeps primary article content, discards nav/menus/ads."""

import trafilatura

from app.ingestion.structure import StructuredBlock


def extract_url(url: str) -> list[StructuredBlock]:
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise ValueError(f"Could not fetch URL: {url}")

    extracted = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not extracted:
        raise ValueError(f"No extractable content found at URL: {url}")

    blocks: list[StructuredBlock] = []
    current_section: str | None = None
    for line in extracted.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_section = line.lstrip("#").strip()
            blocks.append(StructuredBlock(kind="title", text=current_section, section=current_section))
        else:
            blocks.append(StructuredBlock(kind="paragraph", text=line, section=current_section))

    return blocks
