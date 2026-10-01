"""Git repository traversal via GitPython (4.3) — text/source files only, excluding
binaries and dependency/build directories."""

import re
import tempfile
from pathlib import Path

from git import Repo

from app.ingestion.structure import StructuredBlock

EXCLUDED_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv",
    "target", ".next", ".turbo", "vendor", "coverage",
}

# Generated dependency manifests: huge, low-signal, and noisy for retrieval.
EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum", "Pipfile.lock",
}

# Extensions treated as text/source; everything else is skipped as binary.
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".mdx", ".txt", ".rst",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".java", ".go", ".rs",
    ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs", ".sql", ".sh", ".html",
    ".css", ".scss",
}

MAX_FILE_BYTES = 1_000_000  # skip anything absurdly large (likely generated/binary)

# Files with real headings worth splitting on, instead of the one-blob-per-file
# fallback used for everything else (code, JSON, etc. have no such structure).
MARKDOWN_EXTENSIONS = {".md", ".mdx"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def _iter_repo_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        yield path


def extract_repo(repo_url_or_path: str) -> dict[str, list[StructuredBlock]]:
    """Returns a mapping of relative file path -> structured blocks for that file,
    so each file can become its own source_id/section grouping downstream."""

    if repo_url_or_path.startswith(("http://", "https://", "git@")):
        with tempfile.TemporaryDirectory() as tmp:
            Repo.clone_from(repo_url_or_path, tmp, depth=1)
            return _extract_from_dir(Path(tmp))
    else:
        return _extract_from_dir(Path(repo_url_or_path))


def _parse_markdown_blocks(rel_path: str, text: str) -> list[StructuredBlock]:
    """Splits a Markdown file by its `#`/`##`/... headings so a section like
    "## Quick Start" becomes its own title block the chunker can group
    content under - instead of the whole file landing as one opaque blob
    (the fallback below, used for every non-Markdown repo file). Tracks
    fenced code blocks so a '#' inside a shell comment or code sample is
    never mistaken for a heading.
    """
    blocks: list[StructuredBlock] = [StructuredBlock(kind="title", text=rel_path, section=rel_path)]

    current_heading = rel_path
    body_lines: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(body_lines).strip()
        if body:
            blocks.append(StructuredBlock(kind="paragraph", text=body, section=current_heading))
        body_lines.clear()

    for line in text.splitlines():
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            body_lines.append(line)
            continue
        if not in_fence:
            match = _HEADING_RE.match(line)
            if match:
                flush()
                current_heading = match.group(2).strip()
                blocks.append(StructuredBlock(kind="title", text=current_heading, section=current_heading))
                continue
        body_lines.append(line)

    flush()
    return blocks


def _extract_from_dir(root: Path) -> dict[str, list[StructuredBlock]]:
    results: dict[str, list[StructuredBlock]] = {}
    for path in _iter_repo_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel_path = str(path.relative_to(root))
        if path.suffix.lower() in MARKDOWN_EXTENSIONS:
            blocks = _parse_markdown_blocks(rel_path, text)
        else:
            blocks = [
                StructuredBlock(kind="title", text=rel_path, section=rel_path),
                StructuredBlock(kind="paragraph", text=text, section=rel_path),
            ]
        results[rel_path] = blocks
    return results
