"""Memoria persistente de conversaciones vía Mem0.

Reutiliza el bge-m3 ya cargado por app/embeddings/text.py como embedder (en
vez de que Mem0 cargue su propia instancia por separado) y el mismo LLM que
usa el chat (opencode/ollama) para extraer los hechos memorizables. El vector
store es Qdrant en modo embebido (sin servidor), persistido en disco.

Mem0 aísla las memorias por `project` (nuestro project_id, prefijado) vía el
filtro `user_id`, y agrupa los turnos de una conversación con `run_id`
(nuestro session_id). Todas las funciones son best-effort: si Mem0 falla, el
chat sigue funcionando sin memoria (solo se registra una advertencia).
"""

import asyncio
import logging
from functools import lru_cache
from typing import Any

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.embeddings.base import EmbeddingBase
from openai import OpenAI

from app.config import settings
from app.embeddings.text import TEXT_EMBEDDING_DIM, embed_text, embed_texts

logger = logging.getLogger(__name__)


class _SharedTextEmbedder(EmbeddingBase):
    """Delega en el bge-m3 ya cacheado por app/embeddings/text.py en vez de
    instanciar un segundo SentenceTransformer (el embedder "huggingface" de
    Mem0 carga el suyo propio, duplicando ~2 GB de RAM)."""

    def embed(self, text: str, memory_action: str | None = None) -> list[float]:
        return embed_text(text)

    def embed_batch(self, texts: list[str], memory_action: str = "add") -> list[list[float]]:
        return embed_texts(texts)


def _build_opencode_client() -> OpenAI:
    # OpenCode Zen exige el header x-opencode-session o rechaza la request
    # con 400 MissingSessionID; el cliente OpenAI-compatible que arma Mem0
    # por defecto no lo manda.
    return OpenAI(
        api_key=settings.opencode_api_key,
        base_url=settings.opencode_base_url,
        default_headers={"x-opencode-session": "mem0-chat-memory"},
    )


def _llm_config() -> dict[str, Any]:
    if settings.llm_provider == "opencode":
        return {
            "provider": "openai",
            "config": {
                "model": settings.opencode_model,
                "api_key": settings.opencode_api_key,
                "openai_base_url": settings.opencode_base_url,
            },
        }
    return {
        "provider": "ollama",
        "config": {
            "model": settings.ollama_model,
            "ollama_base_url": settings.ollama_base_url,
        },
    }


@lru_cache(maxsize=1)
def _get_memory() -> Memory:
    config = MemoryConfig(
        vector_store={
            "provider": "qdrant",
            "config": {
                "collection_name": "rag_lab_chat_memory",
                "embedding_model_dims": TEXT_EMBEDDING_DIM,
                "path": settings.mem0_qdrant_path,
            },
        },
        # Por defecto Mem0 escribe este historial de auditoría (ADD/UPDATE/
        # DELETE) en ~/.mem0/history.db, fuera del proyecto. Lo mantenemos
        # junto al Qdrant local para que todo el estado de la memoria quede
        # en un solo lugar dentro de rag-lab.
        history_db_path=settings.mem0_history_db_path,
        # Nunca se usa: se reemplaza por _SharedTextEmbedder abajo. Pero la
        # construcción por defecto (sin api_key) hace que el SDK de openai
        # falle al instanciar el cliente, así que hay que darle un valor.
        embedder={"provider": "openai", "config": {"api_key": "unused"}},
        llm=_llm_config(),
    )
    memory = Memory(config)
    memory.embedding_model = _SharedTextEmbedder()
    if settings.llm_provider == "opencode":
        memory.llm.client = _build_opencode_client()
    return memory


def _project_name(project_id: str) -> str:
    return f"{settings.mem0_project_prefix}-{project_id}"


async def ensure_session(project_id: str, session_id: str) -> None:
    """No-op: a diferencia de Engram, Mem0 no requiere registrar la sesión
    de antemano (run_id es solo una etiqueta de filtro en add()/search())."""
    return None


async def recall(project_id: str, question: str) -> list[str]:
    """Memorias del proyecto más relevantes para la pregunta (vacío si falla)."""
    if not settings.mem0_enabled:
        return []
    try:
        result = await asyncio.to_thread(
            _get_memory().search,
            question,
            filters={"user_id": _project_name(project_id)},
            limit=settings.mem0_recall_limit,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, cualquier fallo de Mem0 no debe tumbar el chat
        logger.warning("Mem0: recall no disponible: %s", exc)
        return []
    return [
        item["memory"]
        for item in result.get("results", [])
        if item.get("memory")
        and item.get("score", 0) >= settings.mem0_recall_similarity_threshold
    ]


async def remember(
    project_id: str, session_id: str, question: str, answer: str
) -> None:
    """Guarda el turno (pregunta + respuesta); Mem0 decide qué hechos extraer."""
    if not settings.mem0_enabled or not answer.strip():
        return
    try:
        await asyncio.to_thread(
            _get_memory().add,
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
            user_id=_project_name(project_id),
            run_id=session_id,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, cualquier fallo de Mem0 no debe tumbar el chat
        logger.warning("Mem0: no se pudo guardar el turno: %s", exc)
