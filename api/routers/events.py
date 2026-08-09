"""
Events endpoint — المناسبات ضمن مدة الحملة.

GET /api/v1/events?start=YYYY-MM-DD&days=7
يُرجع قائمة المناسبات/الأحداث الواقعة ضمن الفترة ليختار منها المستخدم
عند إنشاء الحملة.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from tools.events_calendar import get_events_in_range

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/")
def list_events(
    start: str = Query(..., description="تاريخ بدء الحملة YYYY-MM-DD"),
    days: int = Query(7, ge=1, le=90, description="عدد أيام الحملة"),
):
    return get_events_in_range(start, days)
