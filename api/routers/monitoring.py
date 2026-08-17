"""
راوتر لوحة المراقبة (Monitoring / Observability Dashboard) — البند 5.16.9.

يعرض مؤشرات الاستهلاك والتكلفة من جدول llm_usage_logs الحقيقي:
  • /monitoring/overview   — ملخص عام (تكلفة، Tokens، نجاح، أخطاء) + اتجاه زمني
  • /monitoring/agents     — استهلاك كل وكيل (طلبات، Tokens، زمن، تكلفة)
  • /monitoring/campaigns  — تكلفة كل حملة (Trace) مجمّعة
  • /monitoring/errors     — أحدث الأخطاء المسجّلة

كل الـ endpoints متاحة للمشرف (super_admin) على كل بيانات النظام، وللمستخدم
العادي على بياناته الخاصة فقط (user_id = المستخدم الحالي) — عبر معامل
scope الذي يُفرض تلقائياً لغير المشرفين بصرف النظر عمّا يُرسله العميل.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from api.routers.auth import get_current_user
from database.models import LLMUsageLog, User, ContentPlan
from database.session import get_db

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _range_start(period: str) -> datetime | None:
    now = datetime.utcnow()
    return {
        "today": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "90d": now - timedelta(days=90),
    }.get(period)


def _scoped_query(db: Session, current: User, period: str):
    q = db.query(LLMUsageLog)
    if current.role != "super_admin":
        q = q.filter(LLMUsageLog.user_id == current.id)
    start = _range_start(period)
    if start:
        q = q.filter(LLMUsageLog.created_at >= start)
    return q


@router.get("/overview")
def get_overview(
    period: str = Query("30d", pattern="^(today|7d|30d|90d|all)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = _scoped_query(db, current, period)

    totals = q.with_entities(
        func.count(LLMUsageLog.id).label("requests"),
        func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
        func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0).label("cost"),
        func.coalesce(func.sum(LLMUsageLog.retry_count), 0).label("retries"),
        func.coalesce(func.avg(LLMUsageLog.duration_ms), 0).label("avg_duration"),
    ).first()

    failed = q.filter(LLMUsageLog.status == "failed").count()
    total_requests = totals.requests or 0
    success_rate = round(((total_requests - failed) / total_requests) * 100, 1) if total_requests else 100.0

    # عدد الحملات (traces) المميزة ضمن النطاق + متوسط تكلفة/زمن الحملة
    campaign_rows = (
        q.filter(LLMUsageLog.content_plan_id.isnot(None))
        .with_entities(
            LLMUsageLog.content_plan_id,
            func.sum(LLMUsageLog.estimated_cost).label("cost"),
            func.sum(LLMUsageLog.duration_ms).label("duration"),
        )
        .group_by(LLMUsageLog.content_plan_id)
        .all()
    )
    campaigns_count = len(campaign_rows)
    avg_campaign_cost = round(sum(r.cost or 0 for r in campaign_rows) / campaigns_count, 4) if campaigns_count else 0
    avg_campaign_duration_ms = round(sum(r.duration or 0 for r in campaign_rows) / campaigns_count, 1) if campaigns_count else 0

    # اتجاه زمني يومي (آخر 14 يوماً ضمن النطاق)
    trend_start = _range_start(period) or (datetime.utcnow() - timedelta(days=14))
    daily = (
        q.filter(LLMUsageLog.created_at >= trend_start)
        .with_entities(
            func.strftime("%Y-%m-%d", LLMUsageLog.created_at).label("day"),
            func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0).label("cost"),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
            func.count(LLMUsageLog.id).label("requests"),
        )
        .group_by("day")
        .order_by("day")
        .all()
    )

    return {
        "period": period,
        "total_cost": round(totals.cost or 0, 4),
        "total_tokens": int(totals.tokens or 0),
        "total_requests": total_requests,
        "avg_duration_ms": round(totals.avg_duration or 0, 1),
        "success_rate": success_rate,
        "failed_requests": failed,
        "retry_count": int(totals.retries or 0),
        "campaigns_count": campaigns_count,
        "avg_campaign_cost": avg_campaign_cost,
        "avg_campaign_duration_ms": avg_campaign_duration_ms,
        "daily_trend": [
            {"day": r.day, "cost": round(r.cost or 0, 4), "tokens": int(r.tokens or 0), "requests": r.requests}
            for r in daily
        ],
    }


@router.get("/agents")
def get_agents_breakdown(
    period: str = Query("30d", pattern="^(today|7d|30d|90d|all)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = _scoped_query(db, current, period)
    rows = (
        q.with_entities(
            LLMUsageLog.agent_name,
            func.count(LLMUsageLog.id).label("requests"),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0).label("cost"),
            func.coalesce(func.avg(LLMUsageLog.duration_ms), 0).label("avg_duration"),
            func.sum(case((LLMUsageLog.status == "failed", 1), else_=0)).label("failed"),
        )
        .group_by(LLMUsageLog.agent_name)
        .order_by(func.sum(LLMUsageLog.estimated_cost).desc())
        .all()
    )
    return [
        {
            "agent_name": r.agent_name,
            "requests": r.requests,
            "tokens": int(r.tokens or 0),
            "cost": round(r.cost or 0, 4),
            "avg_duration_ms": round(r.avg_duration or 0, 1),
            "failed": int(r.failed or 0),
        }
        for r in rows
    ]


@router.get("/campaigns")
def get_campaigns_breakdown(
    period: str = Query("30d", pattern="^(today|7d|30d|90d|all)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = _scoped_query(db, current, period).filter(LLMUsageLog.content_plan_id.isnot(None))
    rows = (
        q.with_entities(
            LLMUsageLog.content_plan_id,
            func.count(LLMUsageLog.id).label("requests"),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0).label("cost"),
            func.coalesce(func.sum(LLMUsageLog.duration_ms), 0).label("duration"),
            func.sum(case((LLMUsageLog.status == "failed", 1), else_=0)).label("failed"),
            func.coalesce(func.sum(LLMUsageLog.retry_count), 0).label("retries"),
        )
        .group_by(LLMUsageLog.content_plan_id)
        .order_by(func.sum(LLMUsageLog.estimated_cost).desc())
        .limit(limit)
        .all()
    )

    plan_ids = [r.content_plan_id for r in rows]
    plans = {p.id: p for p in db.query(ContentPlan).filter(ContentPlan.id.in_(plan_ids)).all()} if plan_ids else {}

    return [
        {
            "content_plan_id": r.content_plan_id,
            "campaign_name": plans[r.content_plan_id].campaign_name if r.content_plan_id in plans else f"حملة #{r.content_plan_id}",
            "requests": r.requests,
            "tokens": int(r.tokens or 0),
            "cost": round(r.cost or 0, 4),
            "duration_ms": round(r.duration or 0, 1),
            "failed": int(r.failed or 0),
            "retries": int(r.retries or 0),
        }
        for r in rows
    ]


@router.get("/errors")
def get_recent_errors(
    period: str = Query("30d", pattern="^(today|7d|30d|90d|all)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = _scoped_query(db, current, period).filter(LLMUsageLog.status == "failed")
    rows = q.order_by(LLMUsageLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "trace_id": r.trace_id,
            "agent_name": r.agent_name,
            "model_name": r.model_name,
            "error_type": r.error_type,
            "retry_count": r.retry_count,
            "created_at": r.created_at,
        }
        for r in rows
    ]
