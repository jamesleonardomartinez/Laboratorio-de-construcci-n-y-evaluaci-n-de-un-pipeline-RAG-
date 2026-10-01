"""bge-m3 text embedding wrapper (3.1). MIT-licensed, 1024-dim output."""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings

TEXT_EMBEDDING_DIM = 1024


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.text_embedding_model)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
