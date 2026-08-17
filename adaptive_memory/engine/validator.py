from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from smart_social_contracts import FeatureRole

from adaptive_memory.models import Insight, InsightStatus, Recommendation

from .learner import ConsolidationConfig


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    min_support: int = 5
    min_confidence_0_1: float = 0.60
    min_direction_consistency_0_1: float = 0.60


class InsightValidator:
    """Prevents one-off SHAP observations from becoming active behavior rules."""

    def __init__(
        self,
        config: ValidationConfig | None = None,
        consolidation_config: ConsolidationConfig | None = None,
    ):
        if config is not None:
            self.config = config
        else:
            source = consolidation_config or ConsolidationConfig()
            self.config = ValidationConfig(
                min_support=source.min_support,
                min_confidence_0_1=source.confidence_threshold,
                min_direction_consistency_0_1=source.min_direction_consistency,
            )

    def validate(self, insight: Insight) -> Insight:
        reasons: list[str] = []
        if insight.feature_role in {
            FeatureRole.CONTEXT,
            FeatureRole.BRAND_CONSTRAINT,
        }:
            reasons.append(
                f"{insight.feature_role.value} features may scope or constrain policies, "
                "but cannot directly become Adaptive Memory instructions"
            )
        if insight.recommendation == Recommendation.MONITOR:
            reasons.append("the observed outcome/direction pattern is not consistent enough")
        if insight.support_count < self.config.min_support:
            reasons.append(
                f"support_count={insight.support_count} is below {self.config.min_support}"
            )
        if insight.confidence_0_1 < self.config.min_confidence_0_1:
            reasons.append(
                f"confidence={insight.confidence_0_1:.3f} is below "
                f"{self.config.min_confidence_0_1:.3f}"
            )
        if (
            insight.direction_consistency_0_1
            < self.config.min_direction_consistency_0_1
        ):
            reasons.append(
                "SHAP-direction consistency is below the configured threshold"
            )

        now = datetime.now(timezone.utc)
        return insight.model_copy(
            update={
                "status": InsightStatus.REJECTED
                if reasons
                else InsightStatus.VALIDATED,
                "validation_reasons": reasons,
                "updated_at": now,
            }
        )
