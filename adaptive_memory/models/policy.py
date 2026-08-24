from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smart_social_contracts import AgentType

from .enums import PolicyReviewDecision, PolicyStatus, Recommendation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    feature_name: str
    feature_value: Any = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    source_insight_id: str
    confidence_0_1: float = Field(ge=0.0, le=1.0)
    recommendation: Recommendation | None = None
    source_support_count: int = Field(default=0, ge=0)
    priority: int = Field(ge=1, le=5)
    is_hard_constraint: bool = False


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    family_id: str | None = None
    brand_id: str
    target_agent: AgentType
    version: int = Field(ge=1)
    rules: list[PolicyRule] = Field(default_factory=list)
    source_insight_ids: list[str] = Field(default_factory=list)
    status: PolicyStatus = PolicyStatus.DRAFT
    human_approval_required: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None
    supersedes_policy_id: str | None = None
    replacement_policy_id: str | None = None

    # Active learned policies are deliberately time-bounded. The review is due
    # before valid_until; the extra grace window prevents a scheduler delay from
    # disabling a policy on the exact review day.
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_at: datetime | None = None
    last_review_at: datetime | None = None
    review_interval_days: int = Field(default=30, ge=1)
    review_grace_days: int = Field(default=15, ge=0)
    minimum_review_posts: int = Field(default=8, ge=1)
    insufficient_review_count: int = Field(default=0, ge=0)
    last_review_decision: PolicyReviewDecision | None = None
    last_review_reason: str | None = None
    expiration_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def default_family_to_policy_id(self) -> "Policy":
        # Backward-compatible for policies stored before lifecycle versioning.
        if not self.family_id:
            self.family_id = self.id
        return self

    def is_effective(self, at: datetime | None = None) -> bool:
        at = as_utc(at or utc_now())
        if self.status != PolicyStatus.ACTIVE:
            return False
        if self.valid_from is not None and at < as_utc(self.valid_from):
            return False
        return self.valid_until is None or at < as_utc(self.valid_until)
