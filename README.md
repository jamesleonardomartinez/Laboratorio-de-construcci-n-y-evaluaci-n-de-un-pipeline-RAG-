# RAG Lab — Multimodal RAG Chat

A self-contained lab: a chat UI where you attach documents/images/audio/video
and ask questions about them, backed by a fully open-source (MIT/Apache-2.0)
model stack and PostgreSQL + pgvector.

## Stack

| Purpose | Choice | License |
|---|---|---|
| Text embeddings | `BAAI/bge-m3` (1024-dim) | MIT |
| Image embeddings | `google/siglip2-base-patch16` (768-dim) | Apache-2.0 |
| Transcription | `openai/whisper-small` | MIT |
| LLM | Llama 3.1 8B / Qwen2.5 7B via Ollama | open |
| Vector store | PostgreSQL 16 + pgvector | — |
| Backend | FastAPI + asyncpg | — |
| Frontend | React + Vite + TypeScript | — |

See `openspec/changes/multimodal-rag-chat-lab/design.md` for the full
architecture rationale (why two pgvector tables, why SSE, why
`BackgroundTasks` over a queue, etc.).

## Quickstart (Docker)

Requires Docker + Docker Compose, ~10GB free disk for model weights, and a
machine that can run a 7-8B LLM plus three smaller ML models concurrently
(see **Hardware** below).

```bash
cd rag-lab
docker compose up --build
```

This starts:
- `postgres` (pgvector) on `localhost:5432`
- `ollama` on `localhost:11434`
- `backend` (FastAPI) on `localhost:8000`
- `frontend` (Vite dev server) on `localhost:5173`

Then pull the LLM into Ollama (one-time, ~4-8GB depending on model):

```bash
docker exec -it rag-lab-ollama ollama pull llama3.1:8b
# or: qwen2.5:7b / mistral:7b
```

Open `http://localhost:5173`, drag a document (PDF, DOCX, TXT, MD, XLSX, CSV,
HTML), image, audio or video into the chat, wait for the
"✅ Listo, N fragmentos indexados" status, then ask a question.

On first upload, the backend will also download the `bge-m3`, `siglip2`, and
`whisper-small` weights into its container cache (a few GB, one-time).

## Environment variables

All have defaults baked into `docker-compose.yml`; override via a `.env`
file in `rag-lab/` or your shell:

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `rag` / `rag` / `rag_lab` | Postgres credentials |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag pulled/served by Ollama |
| `TEXT_EMBEDDING_MODEL` | `BAAI/bge-m3` | HF model id for text embeddings |
| `IMAGE_EMBEDDING_MODEL` | `google/siglip2-base-patch16-224` | HF model id for image embeddings |
| `WHISPER_MODEL` | `small` | Whisper checkpoint size (`small`/`base`) |
| `VIDEO_FRAME_INTERVAL_SECONDS` | `10` | Key-frame sampling interval for video |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL the frontend calls |

## Local development without Docker

See `backend/SETUP.md` for running the FastAPI app directly in a Python
venv (useful for faster iteration), and run the frontend with:

```bash
cd frontend
npm install
npm run dev
```

Postgres and Ollama still need to be reachable — either run them via
`docker compose up postgres ollama`, or point `DATABASE_URL` /
`OLLAMA_BASE_URL` at your own instances.

## Hardware

Running four models concurrently (bge-m3, SigLIP2, Whisper, and a 7-8B LLM)
is CPU/RAM/GPU-heavy for a lab environment:

- **Minimum**: 16GB RAM, 4+ CPU cores, ~10GB free disk for model weights.
  Expect slow (tens of seconds) LLM responses on CPU-only inference.
- **Recommended**: a GPU with 8GB+ VRAM (for Ollama) speeds up chat
  responses significantly; the embedding/transcription models are small
  enough to run on CPU reasonably.
- If resources are constrained, use `whisper-base` (smaller than `small`)
  and a quantized 7B model (Ollama's default pulls are already quantized).

## Known limitations (see design.md - Risks / Trade-offs)

- Ingestion jobs run via FastAPI `BackgroundTasks`, not a durable queue: a
  backend restart mid-ingestion drops the job (status will not resolve).
- No cross-modal search: you cannot search images by typing a text
  description — SigLIP2 is only used to embed images/frames, not the text
  question, in this lab.
- No authentication — `project_id` partitions data but does not gate access.

## API

```
POST   /projects/{project_id}/upload            # file or link -> ingestion job
GET    /projects/{project_id}/status/{job_id}    # ingestion job status + chunk count
POST   /projects/{project_id}/chat               # question -> SSE stream of answer + sources
GET    /projects/{project_id}/sources            # list indexed sources for the project
```
