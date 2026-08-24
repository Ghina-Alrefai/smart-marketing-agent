from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from smart_social_contracts import AgentType

from .enums import PolicyReviewDecision, PolicyReviewTrigger


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyRuleReviewMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    feature_name: str
    linked_evidence_count: int = Field(ge=0)
    evaluated_post_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_relative_performance_index: float | None = None


class PolicyReview(BaseModel):
    """Immutable audit record for one policy health decision."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    policy_id: str
    family_id: str
    policy_version: int = Field(ge=1)
    brand_id: str
    target_agent: AgentType
    trigger: PolicyReviewTrigger
    decision: PolicyReviewDecision
    reviewed_by: str
    reviewed_at: datetime = Field(default_factory=utc_now)
    evidence_window_start: datetime
    evidence_window_end: datetime
    minimum_required_posts: int = Field(ge=1)
    linked_evidence_count: int = Field(ge=0)
    evaluated_post_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_success_rate_0_1: float | None = Field(default=None, ge=0.0, le=1.0)
    success_rate_delta: float | None = None
    mean_relative_performance_index: float | None = None
    previous_mean_rule_confidence_0_1: float = Field(ge=0.0, le=1.0)
    rule_metrics: list[PolicyRuleReviewMetric] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    replacement_policy_id: str | None = None


class PolicyReviewBatchResult(BaseModel):
    brand_id: str | None = None
    checked_policy_count: int = Field(ge=0)
    reviewed_policy_count: int = Field(ge=0)
    expired_without_review_count: int = Field(ge=0)
    decision_counts: dict[str, int] = Field(default_factory=dict)
    reviews: list[PolicyReview] = Field(default_factory=list)
