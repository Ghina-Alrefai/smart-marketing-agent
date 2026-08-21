"""
Content Plans & Generation endpoints.
The generation pipeline runs in a background thread so the API responds immediately.
"""
from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from api.schemas import (
    ContentPlanCreate,
    ContentPlanOut,
    GeneratedPostOut,
    PostApprovalUpdate,
    GenerationStatusOut,
)
from database.models import (
    ContentPlan,
    GeneratedPost,
    PostPerformanceSnapshot,
    Product,
    ScheduledPost,
)
from database.session import get_db
from config import settings
from tools.db_tools import (
    create_scheduled_post,
    get_scheduled_by_post,
    delete_scheduled_by_post,
)
from workflows.campaign_pipeline import run_campaign_pipeline

router = APIRouter(prefix="/plans", tags=["plans"])
logger = logging.getLogger("smartsocial.plans")

PEAK_HOUR = settings.DEFAULT_SCHEDULE_HOUR


# ── Content Plans ──────────────────────────────────────────────────────────

@router.post("/", response_model=ContentPlanOut, status_code=201)
def create_plan(user_id: int, payload: ContentPlanCreate, db: Session = Depends(get_db)):
    plan = ContentPlan(user_id=user_id, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=ContentPlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan


@router.get("/user/{user_id}", response_model=list[ContentPlanOut])
def list_plans(user_id: int, db: Session = Depends(get_db)):
    return db.query(ContentPlan).filter(ContentPlan.user_id == user_id).all()


# ── Trigger Generation ─────────────────────────────────────────────────────

@router.post("/{plan_id}/generate", response_model=GenerationStatusOut)
def trigger_generation(plan_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    if plan.status == "generating":
        return GenerationStatusOut(plan_id=plan_id, status="generating", message="Already running")

    # مسار توليد واحد موحّد لكل الحملات: campaign_pipeline
    background_tasks.add_task(run_campaign_pipeline, plan_id)
    return GenerationStatusOut(
        plan_id=plan_id, status="started",
        message="بدأت الحملة. تابع الحالة عبر GET /plans/{plan_id}",
    )


@router.get("/{plan_id}/campaign")
def get_campaign_object(plan_id: int, db: Session = Depends(get_db)):
    """كائن الحملة الموحّد النهائي (strategy + products + posts[idea/content/design/review])."""
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan.campaign_data or {"campaign": {"strategy": plan.strategy or {}, "products": [], "posts": []}}


@router.get("/{plan_id}/status", response_model=GenerationStatusOut)
def generation_status(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    posts_count = db.query(GeneratedPost).filter(GeneratedPost.content_plan_id == plan_id).count()

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
    db: Session = Depends(get_db),
):
    """Safely replace partial output from a failed attempt, then run it again."""
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    if plan.status != "failed":
        raise HTTPException(409, "يمكن إعادة التوليد فقط عندما تكون حالة الحملة «فشلت».")

    partial_posts = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.content_plan_id == plan_id)
        .all()
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
            db.query(GeneratedPost).filter(
                GeneratedPost.id.in_(post_ids)
            ).delete(synchronize_session=False)

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
def list_posts(plan_id: int, db: Session = Depends(get_db)):
    return (
        db.query(GeneratedPost)
        .filter(GeneratedPost.content_plan_id == plan_id)
        .order_by(GeneratedPost.day_number)
        .all()
    )


def _peak_datetime_for(plan: ContentPlan | None, day_number: int) -> datetime:
    """تاريخ بدء الحملة (أو اليوم) + (رقم اليوم-1) عند الساعة 8 مساءً."""
    base = plan.start_date if (plan and plan.start_date) else datetime.utcnow()
    base_date = base.date() if isinstance(base, datetime) else base
    offset = max(0, (day_number or 1) - 1)
    return datetime.combine(base_date, time(hour=PEAK_HOUR)) + timedelta(days=offset)


@router.patch("/posts/{post_id}/approve", response_model=GeneratedPostOut)
def approve_post(post_id: int, payload: PostApprovalUpdate, db: Session = Depends(get_db)):
    post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    post.approved = payload.approved
    post.status = "approved" if payload.approved else "rejected"

    if payload.approved:
        # جدولة تلقائية عند الاعتماد (إن لم يكن مجدولاً مسبقاً) على وقت الذروة
        if not get_scheduled_by_post(post.id):
            plan = db.query(ContentPlan).filter(ContentPlan.id == post.content_plan_id).first()
            when = _peak_datetime_for(plan, post.day_number)
            create_scheduled_post(
                user_id=(plan.user_id if plan else post.content_plan_id),
                hook=post.hook or "", caption=post.caption or "", cta=post.cta or "",
                hashtags=post.hashtags or [], image_url=post.image_url or "",
                scheduled_at=when, time_text=f"وقت الذروة {PEAK_HOUR}:00 مساءً",
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
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    posts = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.content_plan_id == plan_id)
        .all()
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
            db.query(GeneratedPost).filter(
                GeneratedPost.id.in_(post_ids)
            ).delete(synchronize_session=False)

        for product_id, removed_count in product_counts.items():
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                product.post_count = max(0, (product.post_count or 0) - removed_count)
                product.is_marketed = product.post_count > 0

        db.delete(plan)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("campaign.delete_failed plan_id=%s", plan_id)
        raise HTTPException(500, "تعذّر حذف الحملة بأمان.")
