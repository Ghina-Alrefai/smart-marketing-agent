"""
Scheduled Posts endpoints — قسم «المجدولة».
يعرض المنشورات التي جدولها المستخدم (عبر الشات/وكيل الجدولة).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ScheduledPostOut, ScheduledTimeUpdate
from tools.db_tools import (
    list_scheduled_posts,
    delete_scheduled_post,
    update_scheduled_time,
)

router = APIRouter(prefix="/scheduled", tags=["scheduled"])


@router.get("/user/{user_id}", response_model=list[ScheduledPostOut])
def list_scheduled(user_id: int):
    return list_scheduled_posts(user_id)


@router.patch("/{scheduled_id}/time")
def edit_scheduled_time(scheduled_id: int, payload: ScheduledTimeUpdate):
    """تعديل وقت نشر منشور مجدول."""
    when = payload.scheduled_at
    if not update_scheduled_time(scheduled_id, when, when.strftime("%Y-%m-%d %H:%M")):
        raise HTTPException(404, "المنشور المجدول غير موجود")
    return {"ok": True, "scheduled_at": when.isoformat()}


@router.delete("/{scheduled_id}", status_code=204)
def cancel_scheduled(scheduled_id: int):
    if not delete_scheduled_post(scheduled_id):
        raise HTTPException(404, "المنشور المجدول غير موجود")
