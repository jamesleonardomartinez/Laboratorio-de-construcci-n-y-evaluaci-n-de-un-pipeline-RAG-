"""5.6 Chat endpoint — SSE stream of the RAG answer plus source citations."""

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.chat.service import stream_chat_answer

router = APIRouter(prefix="/projects/{project_id}", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/chat")
async def chat(project_id: str, body: ChatRequest):
    session_id = body.session_id or project_id
    return StreamingResponse(
        stream_chat_answer(project_id, body.question, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
