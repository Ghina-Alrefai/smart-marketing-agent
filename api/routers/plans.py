"""
Content Plans & Generation endpoints.
The generation pipeline runs in a background thread so the API responds immediately.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from api.schemas import (
    ContentPlanCreate,
    ContentPlanOut,
    GeneratedPostOut,
    PostApprovalUpdate,
    GenerationStatusOut,
)
from database.models import ContentPlan, GeneratedPost
from database.session import get_db
from workflows.generate_content_plan import run_content_generation_pipeline

router = APIRouter(prefix="/plans", tags=["plans"])


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

    background_tasks.add_task(run_content_generation_pipeline, plan_id)

    return GenerationStatusOut(
        plan_id=plan_id,
        status="started",
        message="التوليد بدأ. يمكنك متابعة الحالة عبر GET /plans/{plan_id}",
    )


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


@router.patch("/posts/{post_id}/approve", response_model=GeneratedPostOut)
def approve_post(post_id: int, payload: PostApprovalUpdate, db: Session = Depends(get_db)):
    post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    post.approved = payload.approved
    post.status = "approved" if payload.approved else "rejected"
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    db.query(GeneratedPost).filter(GeneratedPost.content_plan_id == plan_id).delete()
    db.delete(plan)
    db.commit()
