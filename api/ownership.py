"""Shared authorization helpers for user-owned API resources.

Router-level authentication proves that a request has a valid session.  These
helpers perform the second, equally important check: the authenticated account
must own the concrete brand/product/plan/post being accessed.  Super-admins
retain their existing cross-account support access.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.routers.auth import ensure_owner
from database.models import (
    Brand,
    ContentPlan,
    GeneratedPost,
    Product,
    ScheduledPost,
    User,
)


def require_user(user_id: int, current: User, db: Session) -> User:
    ensure_owner(user_id, current)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_brand(brand_id: int, current: User, db: Session) -> Brand:
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    ensure_owner(brand.user_id, current)
    return brand


def require_product(product_id: int, current: User, db: Session) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    ensure_owner(product.user_id, current)
    return product


def require_plan(plan_id: int, current: User, db: Session) -> ContentPlan:
    plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    ensure_owner(plan.user_id, current)
    return plan


def require_generated_post(
    post_id: int, current: User, db: Session
) -> tuple[GeneratedPost, ContentPlan]:
    post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    plan = db.query(ContentPlan).filter(ContentPlan.id == post.content_plan_id).first()
    if plan is None:
        raise HTTPException(status_code=409, detail="Post is not linked to a valid plan")
    ensure_owner(plan.user_id, current)
    return post, plan


def require_scheduled_post(
    scheduled_id: int, current: User, db: Session
) -> ScheduledPost:
    post = db.query(ScheduledPost).filter(ScheduledPost.id == scheduled_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="المنشور المجدول غير موجود")
    ensure_owner(post.user_id, current)
    return post
