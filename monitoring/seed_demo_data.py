"""
يولّد بيانات استهلاك وهمية واقعية داخل جدول llm_usage_logs الحقيقي،
لعرض لوحة المراقبة بأرقام منطقية قبل تجميع بيانات فعلية من حملات حقيقية.

الاستخدام:
    python -m monitoring.seed_demo_data          # يضيف بيانات آمنة للتكرار (idempotent)
    python -m monitoring.seed_demo_data --wipe    # يمسح بيانات المراقبة القديمة أولاً

لا يُنشئ مستخدمين أو حملات وهمية — يُلحق سجلات الاستهلوك بأول مستخدم
وأول حملة موجودين فعلاً في قاعدة البيانات (أو يُنشئ حملة تجريبية واحدة
إن لم توجد حملات على الإطلاق)، فتبقى الأرقام مرتبطة ببيانات حقيقية.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from database.models import Brand, ContentPlan, LLMUsageLog, User
from database.session import SessionLocal, init_db
from monitoring.pricing import calculate_cost

random.seed(42)  # نتائج قابلة لإعادة التوليد بين التشغيلات

AGENTS = [
    ("brand_agent",    "gemini-2.5-flash", 1),
    ("strategy_agent", "gemini-2.5-flash", 1),
    ("product_agent",  "gemini-2.5-flash", 1),
    ("idea_agent",      "gemini-2.5-flash", 1),
    ("content_agent",  "gemini-2.5-flash", 5),
    ("design_agent",   "gemini-3.1-flash-image", 5),
    ("review_agent",   "gemini-2.5-flash", 5),
    ("orchestrator_agent", "gemini-2.5-flash", 3),
]

ERROR_TYPES = ["ServiceUnavailable", "RateLimitError", "ValidationError"]


def _make_log(*, trace_id, user_id, content_plan_id, agent_name, model_name, created_at) -> LLMUsageLog:
    input_tokens = random.randint(300, 2200)
    output_tokens = random.randint(150, 1600)
    duration_ms = random.uniform(400, 6000)
    failed = random.random() < 0.045          # ~4.5% معدل فشل واقعي
    retry_count = 1 if (failed and random.random() < 0.6) else 0

    status = "failed" if failed else "success"
    cost = 0.0 if failed and retry_count == 0 else calculate_cost(input_tokens, output_tokens, model_name)

    return LLMUsageLog(
        trace_id=trace_id,
        span_id=f"span_{random.getrandbits(64):016x}",
        user_id=user_id,
        content_plan_id=content_plan_id,
        agent_name=agent_name,
        model_name=model_name,
        started_at=created_at,
        completed_at=created_at + timedelta(milliseconds=duration_ms),
        duration_ms=round(duration_ms, 1),
        input_tokens=0 if failed and retry_count == 0 else input_tokens,
        output_tokens=0 if failed and retry_count == 0 else output_tokens,
        total_tokens=0 if failed and retry_count == 0 else input_tokens + output_tokens,
        estimated_cost=cost,
        status=status,
        retry_count=retry_count,
        error_type=random.choice(ERROR_TYPES) if failed else None,
        created_at=created_at,
    )


def seed(db, *, user_id: int, content_plan_ids: list[int], days_back: int = 30) -> int:
    """يولّد سجلات موزّعة على `days_back` يوماً الماضية، عبر حملات متعددة."""
    now = datetime.utcnow()
    rows: list[LLMUsageLog] = []

    for day_offset in range(days_back, -1, -1):
        day = now - timedelta(days=day_offset)
        # عدد الحملات المنفَّذة في هذا اليوم يتفاوت (نشاط أعلى في أيام العمل)
        is_weekday = day.weekday() < 5
        campaigns_today = random.randint(1, 4) if is_weekday else random.randint(0, 2)

        for _ in range(campaigns_today):
            plan_id = random.choice(content_plan_ids)
            trace_id = f"trace_{random.getrandbits(64):016x}"
            base_time = day.replace(
                hour=random.randint(9, 22), minute=random.randint(0, 59), second=0, microsecond=0
            )
            cursor = base_time
            for agent_name, model_name, call_count in AGENTS:
                for _ in range(call_count):
                    cursor += timedelta(seconds=random.uniform(1, 20))
                    rows.append(_make_log(
                        trace_id=trace_id, user_id=user_id, content_plan_id=plan_id,
                        agent_name=agent_name, model_name=model_name, created_at=cursor,
                    ))

    db.bulk_save_objects(rows)
    db.commit()
    return len(rows)


def _ensure_demo_campaign(db) -> tuple[int, list[int]]:
    """يعيد (user_id, [content_plan_id, ...]) صالحة لربط البيانات الوهمية بها."""
    user = db.query(User).order_by(User.id).first()
    if user is None:
        raise RuntimeError("لا يوجد أي مستخدم في قاعدة البيانات — أنشئ حساباً أولاً (seed_admin عبر main.py).")

    plans = db.query(ContentPlan).filter(ContentPlan.user_id == user.id).all()
    if plans:
        return user.id, [p.id for p in plans]

    brand = db.query(Brand).filter(Brand.user_id == user.id).first()
    if brand is None:
        brand = Brand(user_id=user.id, brand_name="(تجريبي) براند العرض التوضيحي")
        db.add(brand)
        db.commit()
        db.refresh(brand)

    demo_plans = []
    for i in range(1, 4):
        plan = ContentPlan(
            user_id=user.id, brand_id=brand.id,
            campaign_name=f"حملة تجريبية #{i}", days=7, status="done",
            created_at=datetime.utcnow() - timedelta(days=30 - i * 7),
        )
        db.add(plan)
        demo_plans.append(plan)
    db.commit()
    for p in demo_plans:
        db.refresh(p)
    return user.id, [p.id for p in demo_plans]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo monitoring data")
    parser.add_argument("--wipe", action="store_true", help="يمسح سجلات llm_usage_logs الحالية قبل التوليد")
    parser.add_argument("--days", type=int, default=30, help="عدد الأيام الماضية للتوليد (افتراضي 30)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.wipe:
            deleted = db.query(LLMUsageLog).delete()
            db.commit()
            print(f"[Seed] حُذف {deleted} سجل قديم من llm_usage_logs")

        user_id, plan_ids = _ensure_demo_campaign(db)
        count = seed(db, user_id=user_id, content_plan_ids=plan_ids, days_back=args.days)
        print(f"[Seed] أُنشئ {count} سجل استهلاك تجريبي على {len(plan_ids)} حملة/حملات، للمستخدم #{user_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
