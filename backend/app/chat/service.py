"""5.6/5.7/5.8: retrieval + prompt + LLM call (OpenCode Zen / Ollama), streamed
via SSE, with source citations and an explicit no-context fallback."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from app.chat import memory
from app.chat.prompt import build_user_prompt, load_instructions
from app.config import settings
from app.db.repository import (
    ImageSearchResult,
    TextSearchResult,
    search_image_chunks,
    search_text_chunks,
)
from app.embeddings.image import embed_text_siglip
from app.embeddings.text import embed_text

logger = logging.getLogger(__name__)

NO_CONTEXT_MESSAGE = (
    "No encontré información relevante en los documentos indexados de este proyecto "
    "para responder esa pregunta."
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@dataclass
class RetrievalResults:
    text: list[TextSearchResult] = field(default_factory=list)
    image: list[ImageSearchResult] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.text and not self.image


_OCR_SOURCE_TYPES = {"image", "video"}


def _filter_by_relevance(
    results: list, threshold: float, margin: float, ocr_threshold: float | None = None
) -> list:
    """Applies the absolute similarity threshold, then drops anything more
    than `margin` below the best remaining match. Results arrive already
    sorted by similarity (descending), so a single clearly-best chunk for a
    punctual question won't get crowded out by weaker, tangential chunks from
    other sources that still clear the absolute floor.

    `ocr_threshold`, when given, applies to text_chunks whose source_type
    marks them as OCR-derived (image/video) instead of the stricter
    document-prose `threshold` - see retrieval_ocr_similarity_threshold.
    """

    def _floor(result) -> float:
        if ocr_threshold is not None and getattr(result, "source_type", None) in _OCR_SOURCE_TYPES:
            return ocr_threshold
        return threshold

    relevant = [r for r in results if r.similarity >= _floor(r)]
    if not relevant:
        return relevant
    best_score = relevant[0].similarity
    return [r for r in relevant if r.similarity >= best_score - margin]


async def _retrieve(project_id: str, question: str) -> RetrievalResults:
    text_embedding = await asyncio.to_thread(embed_text, question)
    # SigLIP's text tower, not bge-m3: image_chunks embeddings live in SigLIP's
    # 768-dim space, which bge-m3's 1024-dim query vector cannot search.
    image_embedding = await asyncio.to_thread(embed_text_siglip, question)

    text_results, image_results = await asyncio.gather(
        search_text_chunks(project_id, text_embedding, limit=settings.retrieval_top_k),
        search_image_chunks(project_id, image_embedding, limit=settings.retrieval_image_top_k),
    )

    return RetrievalResults(
        text=_filter_by_relevance(
            text_results,
            settings.retrieval_similarity_threshold,
            settings.retrieval_score_margin,
            ocr_threshold=settings.retrieval_ocr_similarity_threshold,
        ),
        image=_filter_by_relevance(
            image_results,
            settings.retrieval_image_similarity_threshold,
            settings.retrieval_image_score_margin,
        ),
    )


_MEMORY_PREVIEW_CHARS = 160


def _memory_preview(memory: str) -> str:
    memory = " ".join(memory.split())
    if len(memory) <= _MEMORY_PREVIEW_CHARS:
        return memory
    return memory[:_MEMORY_PREVIEW_CHARS].rstrip() + "…"


def _citations(results: RetrievalResults) -> list[dict]:
    seen = set()
    citations = []
    for r in results.text:
        key = ("text", r.source_id, r.section)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"source_id": r.source_id, "section": r.section, "modality": "text"})
    for r in results.image:
        key = ("image", r.source_id, r.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"source_id": r.source_id, "section": None, "modality": "image"})
    return citations


async def _stream_opencode(
    session_id: str, system: str, user: str
) -> AsyncIterator[tuple[str, dict]]:
    headers = {
        "Authorization": f"Bearer {settings.opencode_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "rag-lab-backend/1.0",
        "x-opencode-session": session_id,
    }
    body = {
        "model": settings.opencode_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    async with httpx.AsyncClient(base_url=settings.opencode_base_url, timeout=None) as client:
        async with client.stream("POST", "/chat/completions", headers=headers, json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data or data == "[DONE]":
                    continue
                payload = json.loads(data)

                usage = payload.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens") or 0
                    completion_tokens = usage.get("completion_tokens") or 0
                    total_tokens = usage.get("total_tokens") or (
                        prompt_tokens + completion_tokens
                    )
                    logger.info(
                        "OpenCode tokens [model=%s session=%s]: entrada=%s salida=%s total=%s",
                        settings.opencode_model,
                        session_id,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                    )
                    yield (
                        "usage",
                        {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    )

                choices = payload.get("choices") or []
                if not choices:
                    continue
                token = (choices[0].get("delta") or {}).get("content", "")
                if token:
                    yield ("token", {"token": token})


async def _stream_ollama(system: str, user: str) -> AsyncIterator[tuple[str, dict]]:
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=None) as client:
        async with client.stream(
            "POST",
            "/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": user,
                "system": system,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                payload = json.loads(line)
                token = payload.get("response", "")
                if token:
                    yield ("token", {"token": token})
                if payload.get("done"):
                    prompt_tokens = payload.get("prompt_eval_count") or 0
                    completion_tokens = payload.get("eval_count") or 0
                    logger.info(
                        "Ollama tokens [model=%s]: entrada=%s salida=%s",
                        settings.ollama_model,
                        prompt_tokens,
                        completion_tokens,
                    )
                    yield (
                        "usage",
                        {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        },
                    )
                    break


def _stream_llm(session_id: str, system: str, user: str) -> AsyncIterator[tuple[str, dict]]:
    if settings.llm_provider == "opencode":
        return _stream_opencode(session_id, system, user)
    return _stream_ollama(system, user)


async def stream_chat_answer(
    project_id: str, question: str, session_id: str
) -> AsyncIterator[str]:
    await memory.ensure_session(project_id, session_id)

    results, memories = await asyncio.gather(
        _retrieve(project_id, question),
        memory.recall(project_id, question),
    )

    logger.info(
        "Mem0 recall [project=%s session=%s]: %d memoria(s) recuperada(s)",
        project_id,
        session_id,
        len(memories),
    )
    yield _sse(
        "memory",
        {"count": len(memories), "items": [_memory_preview(m) for m in memories]},
    )

    if results.is_empty() and not memories:
        # Requirement: No relevant context available — say so explicitly rather
        # than calling the LLM and risking a fabricated answer. A follow-up or
        # meta question ("de qué hablábamos?") never matches a document chunk
        # by design, so recalled conversation memory alone is enough to proceed.
        yield _sse("sources", {"sources": []})
        yield _sse("token", {"token": NO_CONTEXT_MESSAGE})
        yield _sse("done", {})
        return

    yield _sse("sources", {"sources": _citations(results)})

    system = load_instructions()
    user = build_user_prompt(question, results.text, results.image, memories)
    answer_parts: list[str] = []
    async for event, data in _stream_llm(session_id, system, user):
        if event == "token":
            answer_parts.append(data["token"])
        yield _sse(event, data)

    await memory.remember(project_id, session_id, question, "".join(answer_parts))
    yield _sse("done", {})
