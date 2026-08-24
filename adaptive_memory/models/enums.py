from __future__ import annotations

from enum import Enum


class EvidenceDirection(str, Enum):
    SUPPORTS_SUCCESS = "supports_success"
    OPPOSES_SUCCESS = "opposes_success"
    NEUTRAL = "neutral"


class InsightStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class Recommendation(str, Enum):
    PREFER = "prefer"
    AVOID = "avoid"
    MONITOR = "monitor"


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class PolicyReviewDecision(str, Enum):
    """Auditable outcomes produced by the policy health reviewer."""

    RENEW = "renew"
    MODIFY = "modify"
    SUSPEND = "suspend"
    EXPIRE = "expire"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class PolicyReviewTrigger(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    EVENT_DRIVEN = "event_driven"
