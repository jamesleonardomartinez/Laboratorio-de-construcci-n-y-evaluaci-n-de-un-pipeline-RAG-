"""5.5 Context-grounded prompt builder.

The assistant instructions live in `prompt.md` (next to this file) so they can be
edited without touching code. The file is split at the `## Contexto recuperado`
heading:

    <everything above>   -> system instructions (sent as the "system" message)
    <everything below>   -> user template, filled with {context} and {question}

If the heading is missing, the whole file is treated as system instructions and the
code appends the context/question itself. If the file is missing, a built-in default
is used.
"""

from pathlib import Path

from app.config import settings
from app.db.repository import ImageSearchResult, TextSearchResult

DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompt.md"

CONTEXT_MARKER = "## Contexto recuperado"

_FALLBACK_SYSTEM = (
    "Eres un asistente que responde preguntas sobre los documentos de un proyecto. "
    "Usa el contexto recuperado como fuente principal. Además de responder, genera "
    "contenido derivado (casos de prueba, resúmenes, planes) cuando se te pida, "
    "marcando como 'Supuesto:' cualquier dato que completes."
)


def _format_context(
    text_results: list[TextSearchResult],
    image_results: list[ImageSearchResult],
    has_memories: bool = False,
) -> str:
    parts = [
        f"[source: {r.source_id}{f' / {r.section}' if r.section else ''}]\n{r.content}"
        for r in text_results
    ]
    parts += [
        # The LLM here is text-only: it cannot see the image's pixels. This
        # note lets it acknowledge a semantically-relevant image exists
        # (surfaced to the user as a cited source) without fabricating a
        # visual description it never received.
        f"[imagen relacionada: {r.source_id}] (imagen indexada, semánticamente "
        "relacionada con la pregunta; su contenido visual no es analizado por "
        "este asistente de texto)"
        for r in image_results
    ]
    if not parts:
        if has_memories:
            # A follow-up/meta question ("de qué hablábamos?") never matches a
            # document chunk by design - point the model at the memory block
            # below instead of letting it default to a no-context refusal.
            return (
                "(no hay contexto documental nuevo para esta pregunta; si la "
                "pregunta se refiere a la conversación anterior, respóndela usando "
                "la sección 'Memoria de conversaciones previas')"
            )
        return "(no se encontró contexto relevante)"
    return "\n\n".join(parts)


def _format_memories(memories: list[str]) -> str:
    if not memories:
        return ""
    lines = "\n".join(f"- {memory}" for memory in memories)
    return f"## Memoria de conversaciones previas\n\n{lines}\n\n"


def _load_template() -> str:
    # Read on every call so edits to prompt.md take effect without a restart.
    path = Path(settings.prompt_file) if settings.prompt_file else DEFAULT_PROMPT_PATH
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_SYSTEM


def load_instructions() -> str:
    """The system-instructions part of prompt.md (above the context marker)."""
    template = _load_template()
    idx = template.find(CONTEXT_MARKER)
    if idx == -1:
        return template.strip()
    return template[:idx].strip()


def build_user_prompt(
    question: str,
    text_results: list[TextSearchResult],
    image_results: list[ImageSearchResult] | None = None,
    memories: list[str] | None = None,
) -> str:
    """The user-message part: the context/question template filled in."""
    template = _load_template()
    context = _format_context(text_results, image_results or [], has_memories=bool(memories))
    memory_block = _format_memories(memories or [])

    idx = template.find(CONTEXT_MARKER)
    if idx == -1:
        # No user template in the file: compose the standard one.
        return (
            f"{memory_block}"
            f"## Contexto recuperado\n\n{context}\n\n"
            f"## Pregunta del usuario\n\n{question}\n\n## Respuesta"
        )

    user_template = template[idx:]
    filled = user_template.replace("{context}", context).replace("{question}", question)
    return f"{memory_block}{filled}"


def build_prompt(
    question: str,
    text_results: list[TextSearchResult],
    image_results: list[ImageSearchResult] | None = None,
    memories: list[str] | None = None,
) -> str:
    """Combined single-string prompt (used by providers without a system role)."""
    return f"{load_instructions()}\n\n{build_user_prompt(question, text_results, image_results, memories)}"
