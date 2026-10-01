from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://rag:rag@localhost:5432/rag_lab"

    llm_provider: str = "opencode"  # "opencode" o "ollama"

    # Path to the editable assistant-instructions markdown file.
    # Empty -> app/chat/prompt.md
    prompt_file: str = ""

    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_model: str = "deepseek-v4.1-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    text_embedding_model: str = "BAAI/bge-m3"
    image_embedding_model: str = "google/siglip2-base-patch16-224"
    whisper_model: str = "small"

    video_frame_interval_seconds: int = 10
    upload_dir: str = "/data/uploads"

    retrieval_top_k: int = 5
    # bge-m3 cosine similarity between unrelated Spanish text still sits
    # around 0.3-0.5 (embedding anisotropy), so 0.2 let almost everything
    # through. Raised to a floor where a match is actually on-topic.
    retrieval_similarity_threshold: float = 0.45
    # On top of the absolute threshold: drop any chunk more than this far
    # below the best match's score, so one standout hit for a punctual
    # question isn't diluted by weaker chunks from unrelated sources that
    # still clear the absolute floor.
    retrieval_score_margin: float = 0.08

    # OCR-derived text (screenshots, video frames) is short and fragmented
    # (bullet lists, IDs, raw JSON) rather than prose, so it scores lower
    # against a conversational question than an actual document does at the
    # same relevance - 0.45 was silently discarding on-topic OCR chunks that
    # scored ~0.30-0.38. Applies only to text_chunks whose source_type is
    # "image"/"video"; document prose keeps the stricter 0.45 floor.
    retrieval_ocr_similarity_threshold: float = 0.28

    # Image retrieval uses SigLIP's text encoder to query image_chunks (a
    # separate, cross-modal embedding space from bge-m3's text-text cosine
    # scores), so it gets its own top_k/threshold rather than reusing the
    # text ones.
    retrieval_image_top_k: int = 3
    retrieval_image_similarity_threshold: float = 0.15
    retrieval_image_score_margin: float = 0.1

    # --- Memoria persistente (Mem0: bge-m3 + Qdrant local embebido) ---
    # Reutiliza el mismo modelo de embeddings que el RAG (bge-m3) y el mismo
    # LLM que el chat (opencode/ollama, según llm_provider). La memoria se
    # aísla por proyecto igual que los embeddings: el project_id se prefija
    # para no mezclarse con memorias de otros proyectos en la misma colección.
    mem0_enabled: bool = True
    mem0_qdrant_path: str = ".mem0_qdrant"
    mem0_history_db_path: str = ".mem0_history.db"
    mem0_project_prefix: str = "rag-lab"
    mem0_recall_limit: int = 5
    # Sin este piso, Mem0 siempre manda hasta mem0_recall_limit recuerdos aunque
    # no tengan relación con la pregunta, inflando tokens de entrada en cada
    # turno (a diferencia de retrieval_similarity_threshold, que sí filtra los
    # chunks documentales irrelevantes).
    mem0_recall_similarity_threshold: float = 0.35

    class Config:
        env_file = ".env"


settings = Settings()
