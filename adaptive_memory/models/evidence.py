from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from smart_social_contracts import AgentType, FeatureRole

from .enums import EvidenceDirection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceEvent(BaseModel):
    """Immutable atomic evidence event derived from one post-feature attribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str
    parent_event_id: str
    source_schema_version: str

    brand_id: str
    page_id: str | None = None
    campaign_id: str | None = None
    post_id: str
    observation_window: str
    observed_at: datetime
    created_at: datetime = Field(default_factory=utc_now)

    outcome_source: str = "facebook"
    attribution_source: str = "brand_dna"
    actual_success: bool
    actual_performance: dict[str, Any] = Field(default_factory=dict)

    predicted_success_probability: float = Field(ge=0.0, le=1.0)
    baseline_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str
    explainer_version: str | None = None
    brand_profile_version: str | None = None
    model_quality_roc_auc: float | None = Field(default=None, ge=0.0, le=1.0)

    feature_name: str
    feature_value: Any = None
    feature_value_key: str
    owner_agent: AgentType
    feature_role: FeatureRole
    direction: EvidenceDirection
    raw_shap_log_odds: float
    success_support_0_1: float = Field(ge=0.0, le=1.0)
    success_opposition_0_1: float = Field(ge=0.0, le=1.0)
    importance_0_1: float = Field(ge=0.0, le=1.0)

    context: dict[str, Any] = Field(default_factory=dict)
    human_approval_required: bool = True
