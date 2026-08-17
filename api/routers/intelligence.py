"""Operational API for Stable Brand DNA and governed Adaptive Memory."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from adaptive_memory.models import PolicyStatus
from api.schemas import PolicyActivationCreate, PostPerformanceCreate
from services.brand_intelligence_service import (
    bootstrap_packaged_history,
    get_brand_context,
    initialize_brand_intelligence,
    intelligence_status,
    memory_service,
    record_post_performance,
)


router = APIRouter(prefix="/intelligence", tags=["brand intelligence"])


def _raise_bad_request(exc: Exception) -> None:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 400
    raise HTTPException(status, message) from exc


@router.get("/brands/{brand_id}/status")
def get_status(brand_id: int):
    try:
        return intelligence_status(brand_id)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.get("/brands/{brand_id}/profile")
def get_profile(brand_id: int):
    result = get_brand_context(brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/brands/{brand_id}/initialize")
def initialize(brand_id: int, force: bool = False):
    try:
        return initialize_brand_intelligence(brand_id, force=force)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/bootstrap-history")
def bootstrap_history(brand_id: int):
    try:
        return bootstrap_packaged_history(brand_id)
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/consolidate")
def consolidate(brand_id: int):
    try:
        context = get_brand_context(brand_id)
        if "error" in context:
            raise ValueError(context["error"])
        result = memory_service().consolidate_insights(context["brand_key"])
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/brands/{brand_id}/generate-policies")
def generate_policies(brand_id: int):
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
def activate_policy(policy_id: str, payload: PolicyActivationCreate):
    try:
        policy = memory_service().activate_policy(policy_id, payload.approved_by)
        return policy.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)


@router.post("/posts/{generated_post_id}/performance")
def submit_performance(generated_post_id: int, payload: PostPerformanceCreate):
    try:
        return record_post_performance(generated_post_id, payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _raise_bad_request(exc)
