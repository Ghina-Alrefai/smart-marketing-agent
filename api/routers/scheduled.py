"""
Scheduled Posts endpoints — قسم «المجدولة».
يعرض المنشورات التي جدولها المستخدم (عبر الشات/وكيل الجدولة).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.ownership import require_scheduled_post, require_user
from api.routers.auth import get_current_user
from api.schemas import ScheduledPostOut, ScheduledTimeUpdate
from database.models import User
from database.session import get_db
from tools.db_tools import list_scheduled_posts

router = APIRouter(prefix="/scheduled", tags=["scheduled"])


@router.get("/user/{user_id}", response_model=list[ScheduledPostOut])
def list_scheduled(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_user(user_id, current, db)
    return list_scheduled_posts(user_id)


@router.patch("/{scheduled_id}/time")
def edit_scheduled_time(
    scheduled_id: int,
    payload: ScheduledTimeUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تعديل وقت نشر منشور مجدول."""
    when = payload.scheduled_at
    post = require_scheduled_post(scheduled_id, current, db)
    post.scheduled_at = when
    post.time_text = when.strftime("%Y-%m-%d %H:%M")
    db.commit()
    return {"ok": True, "scheduled_at": when.isoformat()}


@router.delete("/{scheduled_id}", status_code=204)
def cancel_scheduled(
    scheduled_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = require_scheduled_post(scheduled_id, current, db)
    db.delete(post)
    db.commit()
