from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from smart_social_contracts import AgentType

from .enums import PolicyStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    feature_name: str
    feature_value: Any = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    source_insight_id: str
    confidence_0_1: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=1, le=5)
    is_hard_constraint: bool = False


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    brand_id: str
    target_agent: AgentType
    version: int = Field(ge=1)
    rules: list[PolicyRule] = Field(default_factory=list)
    source_insight_ids: list[str] = Field(default_factory=list)
    status: PolicyStatus = PolicyStatus.DRAFT
    human_approval_required: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
