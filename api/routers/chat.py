"""
Chat endpoint (LAYER 0) — بوابة المحادثة مع الـ Orchestrator.

POST /api/v1/chat/message   → يرسل رسالة ويستقبل رداً (نتيجة أو سؤال توضيحي)
GET  /api/v1/chat/session/{id} → يجلب تاريخ الجلسة
DELETE /api/v1/chat/session/{id} → يصفّر الجلسة

لا يمسّ الـ Pipeline — يستدعي فقط طبقة الـ Orchestrator الجديدة.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.orchestrator import session_store as store
from agents.orchestrator.orchestrator_agent import handle_message

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: int
    brand_id: int
    message: str
    session_id: str | None = None
    dry_run: bool = False


@router.post("/message")
def chat_message(payload: ChatRequest):
    if not payload.message.strip():
        raise HTTPException(400, "الرسالة فارغة")
    return handle_message(
        user_id=payload.user_id, brand_id=payload.brand_id,
        message=payload.message, session_id=payload.session_id,
        dry_run=payload.dry_run,
    )


@router.get("/session/{session_id}")
def get_session(session_id: str):
    s = store.get(session_id)
    if not s:
        raise HTTPException(404, "الجلسة غير موجودة")
    return {"session_id": s.id, "intent": s.intent, "slots": s.slots,
            "awaiting": s.awaiting, "history": s.history}


@router.delete("/session/{session_id}", status_code=204)
def delete_session(session_id: str):
    store.reset(session_id)
