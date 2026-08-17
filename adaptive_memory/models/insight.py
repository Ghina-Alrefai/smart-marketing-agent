from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from pydantic import BaseModel, ConfigDict, Field

from smart_social_contracts import AgentType, FeatureRole

from .enums import InsightStatus, Recommendation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def insight_id_for(group_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"smart-social-insight:{group_key}"))


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    group_key: str
    brand_id: str
    target_agent: AgentType
    feature_name: str
    feature_value: Any = None
    feature_role: FeatureRole
    recommendation: Recommendation
    description: str
    context_conditions: dict[str, Any] = Field(default_factory=dict)

    evidence_ids: list[str]
    support_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    actual_success_rate_0_1: float = Field(ge=0.0, le=1.0)
    direction_consistency_0_1: float = Field(ge=0.0, le=1.0)
    mean_success_support_0_1: float = Field(ge=0.0, le=1.0)
    mean_failure_opposition_0_1: float = Field(ge=0.0, le=1.0)
    mean_importance_0_1: float = Field(ge=0.0, le=1.0)
    confidence_0_1: float = Field(ge=0.0, le=1.0)
    source_model_versions: list[str] = Field(default_factory=list)

    status: InsightStatus = InsightStatus.CANDIDATE
    validation_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(days=60)
    )
