from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from smart_social_contracts import AgentType, FeatureRole, get_feature_spec

from .enums import EvidenceDirection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AttributionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_source: str = "facebook"
    attribution_source: str = "brand_dna"


class ActualPerformance(BaseModel):
    model_config = ConfigDict(extra="allow")

    relative_performance_index: float | None = None
    weighted_engagement: float | None = None
    reactions: float | None = None
    comments: float | None = None
    shares: float | None = None
    reach: float | None = None
    clicks: float | None = None


class FeatureAttributionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: str
    value: Any = None
    direction: EvidenceDirection
    raw_shap_log_odds: float
    success_support_0_1: float = Field(ge=0.0, le=1.0)
    success_opposition_0_1: float = Field(ge=0.0, le=1.0)
    importance_0_1: float = Field(ge=0.0, le=1.0)
    owner_agent: AgentType | None = None
    feature_role: FeatureRole | None = None

    @field_validator("value")
    @classmethod
    def value_must_be_json_serializable(cls, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("feature value must be JSON serializable") from exc
        return value

    @model_validator(mode="after")
    def registry_must_match(self) -> "FeatureAttributionInput":
        spec = get_feature_spec(self.feature)
        if self.owner_agent is not None and self.owner_agent != spec.owner_agent:
            raise ValueError(
                f"owner_agent for {self.feature!r} must be {spec.owner_agent.value}"
            )
        if self.feature_role is not None and self.feature_role != spec.role:
            raise ValueError(
                f"feature_role for {self.feature!r} must be {spec.role.value}"
            )
        self.owner_agent = spec.owner_agent
        self.feature_role = spec.role
        return self


class BrandDNAEvidenceEnvelopeV1(BaseModel):
    """Versioned public contract received from Brand-DNA.

    The model deliberately preserves SHAP attribution fields as attribution fields;
    none of them is called confidence.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: str = "brand-dna-am-evidence-v1"
    event_id: str | None = None
    evidence_type: str
    source: AttributionSource | str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    observed_at: datetime | None = None
    observation_window: str = "24h"

    brand_id: str | None = None
    page_id: str | None = None
    campaign_id: str | None = None
    post_id: str
    context: dict[str, Any] = Field(default_factory=dict)

    brand_profile_version: str | None = None
    model_version: str
    explainer_version: str | None = None
    model_quality: dict[str, Any] = Field(default_factory=dict)

    actual_success: bool
    actual_performance: ActualPerformance = Field(default_factory=ActualPerformance)
    predicted_success_probability: float = Field(ge=0.0, le=1.0)
    baseline_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    shap_units: str = "log_odds"
    human_approval_required: bool = True

    feature_attributions: list[FeatureAttributionInput]

    @field_validator("brand_id", "page_id", "campaign_id", "event_id", mode="before")
    @classmethod
    def empty_strings_to_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_semantics(self) -> "BrandDNAEvidenceEnvelopeV1":
        expected_type = (
            "post_success_feature_attribution"
            if self.actual_success
            else "post_failure_feature_attribution"
        )
        if self.evidence_type != expected_type:
            raise ValueError(
                f"evidence_type must be {expected_type!r} when actual_success={self.actual_success}"
            )
        if not self.feature_attributions:
            raise ValueError("feature_attributions cannot be empty")
        self.observed_at = self.observed_at or self.created_at
        return self
