"""Operational API for Stable Brand DNA and governed Adaptive Memory."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from adaptive_memory.models import PolicyStatus
from api.ownership import require_brand, require_generated_post
from api.routers.auth import get_current_user
from api.schemas import (
    PolicyActivationCreate,
    PolicyReviewBatchCreate,
    PolicyReviewCreate,
    PostPerformanceCreate,
)
from database.models import Brand, GeneratedPost, User
from database.session import get_db
from services.brand_intelligence_service import (
    bootstrap_packaged_history,
    brand_key,
    get_brand_context,
    initialize_brand_intelligence,
    intelligence_status,
    memory_service,
    record_post_performance,
)


router = APIRouter(prefix="/intelligence", tags=["brand intelligence"])


def _owned_brand(
    brand_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Brand:
    return require_brand(brand_id, current, db)


def _owned_generated_post(
    generated_post_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedPost:
    post, _plan = require_generated_post(generated_post_id, current, db)
    return post


def _owned_policy(
    policy_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = memory_service().storage.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy {policy_id!r} does not exist")
    if current.role == "super_admin":
        return policy

    query = db.query(Brand).filter(Brand.user_id == current.id)
    if not any(brand_key(brand) == policy.brand_id for brand in query.all()):
        raise HTTPException(403, "لا يمكنك الوصول إلى سياسة تخص براند آخر")
    return policy


def _raise_bad_request(exc: Exception) -> None:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 400
    raise HTTPException(status, message) from exc


@router.get("/brands/{brand_id}/status")
def get_status(brand_id: int, _brand: Brand = Depends(_owned_brand)):
    try:
        return intelligence_status(brand_id)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.get("/brands/{brand_id}/profile")
def get_profile(brand_id: int, _brand: Brand = Depends(_owned_brand)):
    result = get_brand_context(brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/brands/{brand_id}/initialize")
def initialize(
    brand_id: int,
    force: bool = False,
    _brand: Brand = Depends(_owned_brand),
):
    try:
        return initialize_brand_intelligence(brand_id, force=force)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/bootstrap-history")
def bootstrap_history(brand_id: int, _brand: Brand = Depends(_owned_brand)):
    try:
        return bootstrap_packaged_history(brand_id)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/consolidate")
def consolidate(brand_id: int, _brand: Brand = Depends(_owned_brand)):
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        result = memory_service().consolidate_insights(context["brand_key"])
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/generate-policies")
def generate_policies(brand_id: int, _brand: Brand = Depends(_owned_brand)):
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        policies = memory_service().generate_draft_policies(context["brand_key"])
        return {
            "created_count": len(policies),
            "policies": [item.model_dump(mode="json") for item in policies],
            "activation_note": "Drafts are inert until a human explicitly activates them.",
        }
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.get("/brands/{brand_id}/policies")
def list_policies(
    brand_id: int,
    status: str | None = Query(default=None),
    _brand: Brand = Depends(_owned_brand),
):
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        parsed_status = PolicyStatus(status) if status else None
        policies = memory_service().storage.list_policies(
            brand_id=context["brand_key"], status=parsed_status
        )
        return [item.model_dump(mode="json") for item in policies]
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/policies/{policy_id}/activate")
def activate_policy(
    policy_id: str,
    payload: PolicyActivationCreate,
    _policy=Depends(_owned_policy),
):
    try:
        policy = memory_service().activate_policy(policy_id, payload.approved_by)
        return policy.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/review-policies")
def review_due_policies(
    brand_id: int,
    payload: PolicyReviewBatchCreate,
    _brand: Brand = Depends(_owned_brand),
):
    """Run all reviews that are due for this brand; early policies are untouched."""
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        result = memory_service().review_due_policies(
            context["brand_key"], reviewed_by=payload.reviewed_by
        )
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/policies/{policy_id}/review")
def review_policy(
    policy_id: str,
    payload: PolicyReviewCreate,
    _policy=Depends(_owned_policy),
):
    """Human-triggered early/due review using the same evidence gates as scheduler."""
    try:
        result = memory_service().review_policy(
            policy_id,
            reviewed_by=payload.reviewed_by,
            force=payload.force,
        )
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.get("/brands/{brand_id}/policy-reviews")
def list_policy_reviews(
    brand_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    _brand: Brand = Depends(_owned_brand),
):
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        reviews = memory_service().list_policy_reviews(
            brand_id=context["brand_key"], limit=limit
        )
        return [item.model_dump(mode="json") for item in reviews]
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/posts/{generated_post_id}/performance")
def submit_performance(
    generated_post_id: int,
    payload: PostPerformanceCreate,
    _post: GeneratedPost = Depends(_owned_generated_post),
):
    try:
        return record_post_performance(generated_post_id, payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)
