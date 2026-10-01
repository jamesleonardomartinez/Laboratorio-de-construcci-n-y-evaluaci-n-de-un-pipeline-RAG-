# Backend local development (without Docker)

Requires Python 3.11 and `ffmpeg` (needed for audio/video handling). On Windows
without a package manager, install it with pip:

```bash
pip install ffmpeg-downloader
ffdl install --add-path
```

The app also resolves the ffmpeg binaries from the persistent PATH automatically
(see `app/ffmpeg_utils.py`), so a terminal restart is not required.

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Environment variables (see docker-compose.yml for defaults)
export DATABASE_URL=postgresql://rag:rag@localhost:5432/rag_lab

# LLM: usa la API de OpenCode Go con el modelo DeepSeek
export LLM_PROVIDER=opencode
export OPENCODE_API_KEY=tu_api_key_de_opencode
export OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1
export OPENCODE_MODEL=deepseek-v4.1-flash

# Alternativa local (LLM_PROVIDER=ollama)
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1:8b

# Memoria persistente (Engram). Requiere el binario `engram` y su servidor HTTP:
#   engram serve        # escucha en http://127.0.0.1:7437
# Sin él, el chat funciona igual: simplemente no recuerda conversaciones previas.
export ENGRAM_ENABLED=true
export ENGRAM_URL=http://127.0.0.1:7437
export ENGRAM_PROJECT_PREFIX=rag-lab

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On first run, `sentence-transformers`/`transformers` will download the `bge-m3`,
`siglip2-base-patch16`, and `whisper-small` weights into the local HF cache
(`~/.cache/huggingface`). This can take several minutes and a few GB of disk.

Postgres (with pgvector) still needs to be running — via `docker compose up postgres`
from the repo root, or your own local install. Ollama solo es necesario si usas
`LLM_PROVIDER=ollama`; con `LLM_PROVIDER=opencode` el LLM se sirve desde la API de
OpenCode Go y basta con tener `OPENCODE_API_KEY` configurada.
