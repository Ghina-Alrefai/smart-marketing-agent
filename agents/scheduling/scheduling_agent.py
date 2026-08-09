"""
Scheduling Agent — وكيل جدولة المنشورات في وقت محدد.

مسؤول عن أخذ منشور جاهز (نص + صورة اختيارية) ووقتٍ يحدده المستخدم،
وحفظه في قسم «المجدولة» ليُنشر لاحقاً.

الموقع في الهرمية: منفّذ (L2) تحت publishing_mgr.
"""
from __future__ import annotations

from datetime import datetime


def schedule_post(user_id: int, content: dict, scheduled_at_iso: str | None,
                  time_text: str = "", dry_run: bool = False) -> dict:
    """
    يجدول منشوراً.
      content : {hook, caption, cta, hashtags, image_url}
      scheduled_at_iso : وقت مثل "2026-08-05T18:00" (أو None).
    """
    when = None
    if scheduled_at_iso:
        try:
            when = datetime.fromisoformat(scheduled_at_iso)
        except ValueError:
            when = None

    if dry_run:
        return {"scheduled_id": 0, "scheduled_at": scheduled_at_iso,
                "time_text": time_text, "status": "stub",
                "message": f"(تجريبي) سيُجدول المنشور: {time_text or scheduled_at_iso or 'وقت غير محدد'}"}

    from tools.db_tools import create_scheduled_post
    sid = create_scheduled_post(
        user_id=user_id,
        hook=content.get("hook", ""), caption=content.get("caption", ""),
        cta=content.get("cta", ""), hashtags=content.get("hashtags", []),
        image_url=content.get("image_url", ""),
        scheduled_at=when, time_text=time_text,
    )
    return {"scheduled_id": sid, "scheduled_at": scheduled_at_iso,
            "time_text": time_text, "status": "scheduled",
            "message": f"تمت جدولة المنشور: {time_text or scheduled_at_iso}"}
