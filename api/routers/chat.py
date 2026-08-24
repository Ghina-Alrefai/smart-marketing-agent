"""
Chat endpoint (LAYER 0) — بوابة المحادثة مع الـ Orchestrator.

POST /api/v1/chat/message   → يرسل رسالة ويستقبل رداً (نتيجة أو سؤال توضيحي)
GET  /api/v1/chat/session/{id} → يجلب تاريخ الجلسة
DELETE /api/v1/chat/session/{id} → يصفّر الجلسة

لا يمسّ الـ Pipeline — يستدعي فقط طبقة الـ Orchestrator الجديدة.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.orchestrator import session_store as store
from agents.orchestrator.orchestrator_agent import handle_message
from api.ownership import require_brand, require_user
from api.routers.auth import get_current_user
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: int
    brand_id: int
    message: str
    session_id: str | None = None
    dry_run: bool = False


@router.post("/message")
def chat_message(
    payload: ChatRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.message.strip():
        raise HTTPException(400, "الرسالة فارغة")
    require_user(payload.user_id, current, db)
    brand = require_brand(payload.brand_id, current, db)
    if brand.user_id != payload.user_id:
        raise HTTPException(400, "Brand does not belong to the selected user")
    try:
        return handle_message(
            user_id=payload.user_id, brand_id=payload.brand_id,
            message=payload.message, session_id=payload.session_id,
            dry_run=payload.dry_run,
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/session/{session_id}")
def get_session(
    session_id: str,
    current: User = Depends(get_current_user),
):
    s = store.get(session_id)
    if not s:
        raise HTTPException(404, "الجلسة غير موجودة")
    if current.role != "super_admin" and s.owner_user_id != current.id:
        raise HTTPException(403, "لا يمكنك الوصول إلى جلسة مستخدم آخر")
    return {"session_id": s.id, "intent": s.intent, "slots": s.slots,
            "awaiting": s.awaiting, "history": s.history}


@router.delete("/session/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    current: User = Depends(get_current_user),
):
    session = store.get(session_id)
    if session is None:
        raise HTTPException(404, "الجلسة غير موجودة")
    if current.role != "super_admin" and session.owner_user_id != current.id:
        raise HTTPException(403, "لا يمكنك حذف جلسة مستخدم آخر")
    store.reset(session_id)
