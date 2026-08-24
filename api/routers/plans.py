"""
Content Plans & Generation endpoints.
The generation pipeline runs in a background thread so the API responds immediately.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, time, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from api.ownership import (
    require_brand,
    require_generated_post,
    require_plan,
    require_user,
)
from api.routers.auth import get_current_user
from api.schemas import (
    ContentPlanCreate,
    ContentPlanOut,
    GeneratedPostOut,
    GenerationStatusOut,
    PostApprovalUpdate,
)
from config import settings
from database.models import (
    ContentPlan,
    GeneratedPost,
    LLMUsageLog,
    PostPerformanceSnapshot,
    Product,
    ScheduledPost,
    User,
    utcnow_naive,
)
from database.session import get_db
from tools.db_tools import (
    create_scheduled_post,
    delete_scheduled_by_post,
    get_scheduled_by_post,
)
from workflows.campaign_pipeline import run_campaign_pipeline

router = APIRouter(prefix="/plans", tags=["plans"])
logger = logging.getLogger("smartsocial.plans")

PEAK_HOUR = settings.DEFAULT_SCHEDULE_HOUR


# ── Content Plans ──────────────────────────────────────────────────────────


@router.post("/", response_model=ContentPlanOut, status_code=201)
def create_plan(
    user_id: int,
    payload: ContentPlanCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_user(user_id, current, db)
    brand = require_brand(payload.brand_id, current, db)
    if brand.user_id != user_id:
        raise HTTPException(400, "Brand does not belong to the selected user")

    requested_product_ids = set(payload.product_ids)
    if requested_product_ids:
        owned_product_ids = {
            row[0]
            for row in db.query(Product.id).filter(
                Product.user_id == user_id,
                Product.id.in_(requested_product_ids),
            )
        }
        invalid_ids = sorted(requested_product_ids - owned_product_ids)
        if invalid_ids:
            raise HTTPException(
                400,
                f"Products do not belong to the selected user: {invalid_ids}",
            )

    plan = ContentPlan(user_id=user_id, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/user/{user_id}", response_model=list[ContentPlanOut])
def list_plans(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_user(user_id, current, db)
    return db.query(ContentPlan).filter(ContentPlan.user_id == user_id).all()


@router.get("/{plan_id}", response_model=ContentPlanOut)
def get_plan(
    plan_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_plan(plan_id, current, db)


# ── Trigger Generation ─────────────────────────────────────────────────────


@router.post("/{plan_id}/generate", response_model=GenerationStatusOut)
def trigger_generation(
    plan_id: int,
    background_tasks: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_plan(plan_id, current, db)

    # Claim the plan in the database before queuing work.  The conditional
    # UPDATE makes two concurrent trigger requests race safely: exactly one
    # changes the state and schedules the pipeline; the other sees rowcount 0.
    claimed = (
        db.query(ContentPlan)
        .filter(ContentPlan.id == plan_id, ContentPlan.status != "generating")
        .update(
            {
                ContentPlan.status: "generating",
                ContentPlan.current_stage: "بانتظار بدء التوليد",
                ContentPlan.error_message: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if claimed == 0:
        return GenerationStatusOut(
            plan_id=plan_id, status="generating", message="Already running"
        )

    # مسار توليد واحد موحّد لكل الحملات: campaign_pipeline
    background_tasks.add_task(run_campaign_pipeline, plan_id)
    return GenerationStatusOut(
        plan_id=plan_id,
        status="started",
        message="بدأت الحملة. تابع الحالة عبر GET /plans/{plan_id}",
    )


@router.get("/{plan_id}/campaign")
def get_campaign_object(
    plan_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """كائن الحملة الموحّد النهائي (strategy + products + posts[idea/content/design/review])."""
    plan = require_plan(plan_id, current, db)
    return plan.campaign_data or {
        "campaign": {"strategy": plan.strategy or {}, "products": [], "posts": []}
    }


@router.get("/{plan_id}/status", response_model=GenerationStatusOut)
def generation_status(
    plan_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = require_plan(plan_id, current, db)

    posts_count = (
        db.query(GeneratedPost).filter(GeneratedPost.content_plan_id == plan_id).count()
    )

    return GenerationStatusOut(
        plan_id=plan_id,
        status=plan.status,
        posts_generated=posts_count,
        message=plan.error_message if plan.status == "failed" else None,
        current_stage=plan.current_stage,
        error_message=plan.error_message,
    )


@router.post("/{plan_id}/regenerate", response_model=GenerationStatusOut)
def regenerate_failed_plan(
    plan_id: int,
    background_tasks: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Safely replace partial output from a failed attempt, then run it again."""
    plan = require_plan(plan_id, current, db)
    if plan.status != "failed":
        raise HTTPException(
            409, "يمكن إعادة التوليد فقط عندما تكون حالة الحملة «فشلت»."
        )

    partial_posts = (
        db.query(GeneratedPost).filter(GeneratedPost.content_plan_id == plan_id).all()
    )
    post_ids = [post.id for post in partial_posts]

    # Never destroy human decisions or observed performance evidence.
    if any(post.approved for post in partial_posts):
        raise HTTPException(
            409,
            "لا يمكن إعادة هذه الحملة تلقائياً لأن بعض منشوراتها معتمدة. ألغِ الاعتماد أو أنشئ حملة جديدة.",
        )
    if post_ids and (
        db.query(PostPerformanceSnapshot)
        .filter(PostPerformanceSnapshot.generated_post_id.in_(post_ids))
        .first()
    ):
        raise HTTPException(
            409,
            "لا يمكن حذف المحاولة لأنها تحتوي بيانات أداء محفوظة. أنشئ حملة جديدة للحفاظ على سجل التعلّم.",
        )

    product_counts = Counter(
        post.product_id for post in partial_posts if post.product_id is not None
    )

    try:
        if post_ids:
            db.query(ScheduledPost).filter(
                ScheduledPost.generated_post_id.in_(post_ids)
            ).delete(synchronize_session=False)
            db.query(PostPerformanceSnapshot).filter(
                PostPerformanceSnapshot.generated_post_id.in_(post_ids)
            ).delete(synchronize_session=False)
            db.query(GeneratedPost).filter(GeneratedPost.id.in_(post_ids)).delete(
                synchronize_session=False
            )

        for product_id, removed_count in product_counts.items():
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                continue
            product.post_count = max(0, (product.post_count or 0) - removed_count)
            product.is_marketed = product.post_count > 0

        plan.strategy = {}
        plan.campaign_data = {}
        plan.intelligence_summary = {}
        plan.status = "generating"
        plan.current_stage = "بانتظار إعادة التوليد"
        plan.error_message = None
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("campaign.regeneration_cleanup_failed plan_id=%s", plan_id)
        raise HTTPException(500, "تعذّر تنظيف المحاولة الفاشلة؛ لم تبدأ إعادة التوليد.")

    logger.info(
        "campaign.regeneration_started plan_id=%s removed_partial_posts=%s",
        plan_id,
        len(post_ids),
    )
    background_tasks.add_task(run_campaign_pipeline, plan_id)
    return GenerationStatusOut(
        plan_id=plan_id,
        status="started",
        posts_generated=0,
        current_stage=plan.current_stage,
        message="تم تنظيف المحاولة الفاشلة وبدأت إعادة توليد الحملة.",
    )


# ── Posts ──────────────────────────────────────────────────────────────────


@router.get("/{plan_id}/posts", response_model=list[GeneratedPostOut])
def list_posts(
    plan_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_plan(plan_id, current, db)
    return (
        db.query(GeneratedPost)
        .filter(GeneratedPost.content_plan_id == plan_id)
        .order_by(GeneratedPost.day_number)
        .all()
    )


def _peak_datetime_for(plan: ContentPlan | None, day_number: int) -> datetime:
    """تاريخ بدء الحملة (أو اليوم) + (رقم اليوم-1) عند الساعة 8 مساءً."""
    base = plan.start_date if (plan and plan.start_date) else utcnow_naive()
    base_date = base.date() if isinstance(base, datetime) else base
    offset = max(0, (day_number or 1) - 1)
    return datetime.combine(base_date, time(hour=PEAK_HOUR)) + timedelta(days=offset)


@router.patch("/posts/{post_id}/approve", response_model=GeneratedPostOut)
def approve_post(
    post_id: int,
    payload: PostApprovalUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post, plan = require_generated_post(post_id, current, db)

    post.approved = payload.approved
    post.status = "approved" if payload.approved else "rejected"

    if payload.approved:
        # جدولة تلقائية عند الاعتماد (إن لم يكن مجدولاً مسبقاً) على وقت الذروة
        if not get_scheduled_by_post(post.id):
            when = _peak_datetime_for(plan, post.day_number)
            create_scheduled_post(
                user_id=plan.user_id,
                hook=post.hook or "",
                caption=post.caption or "",
                cta=post.cta or "",
                hashtags=post.hashtags or [],
                image_url=post.image_url or "",
                scheduled_at=when,
                time_text=f"وقت الذروة {PEAK_HOUR}:00 مساءً",
                generated_post_id=post.id,
            )
            post.scheduled_at = when
    else:
        # عند الرفض: أزِل أي جدولة تلقائية سابقة لهذا المنشور
        delete_scheduled_by_post(post.id)
        post.scheduled_at = None

    db.commit()
    db.refresh(post)
    return post


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = require_plan(plan_id, current, db)

    posts = (
        db.query(GeneratedPost).filter(GeneratedPost.content_plan_id == plan_id).all()
    )
    post_ids = [post.id for post in posts]
    product_counts = Counter(
        post.product_id for post in posts if post.product_id is not None
    )

    try:
        # الحذف الجماعي لا يشغّل ORM cascades؛ احذف العلاقات التابعة أولاً
        # كي يعمل الحذف مع SQLite (foreign_keys=ON) وPostgreSQL بالتساوي.
        if post_ids:
            db.query(ScheduledPost).filter(
                ScheduledPost.generated_post_id.in_(post_ids)
            ).delete(synchronize_session=False)
            db.query(PostPerformanceSnapshot).filter(
                PostPerformanceSnapshot.generated_post_id.in_(post_ids)
            ).delete(synchronize_session=False)
            db.query(GeneratedPost).filter(GeneratedPost.id.in_(post_ids)).delete(
                synchronize_session=False
            )

        for product_id, removed_count in product_counts.items():
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                product.post_count = max(0, (product.post_count or 0) - removed_count)
                product.is_marketed = product.post_count > 0

        # Consumption records are audit history and must not be destroyed with
        # a campaign. Detach them first so their nullable foreign key cannot
        # block DELETE on SQLite or PostgreSQL. This also repairs old databases
        # created before the FK gained ON DELETE SET NULL.
        detached_usage_logs = (
            db.query(LLMUsageLog)
            .filter(LLMUsageLog.content_plan_id == plan_id)
            .update(
                {LLMUsageLog.content_plan_id: None},
                synchronize_session=False,
            )
        )

        db.delete(plan)
        db.commit()
        logger.info(
            "campaign.deleted plan_id=%s posts=%s detached_usage_logs=%s",
            plan_id,
            len(post_ids),
            detached_usage_logs,
        )
    except Exception:
        db.rollback()
        logger.exception("campaign.delete_failed plan_id=%s", plan_id)
        raise HTTPException(500, "تعذّر حذف الحملة بأمان.")
