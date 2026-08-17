from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable

from smart_social_contracts import FeatureRole

from adaptive_memory.models import (
    EvidenceDirection,
    EvidenceEvent,
    Insight,
    InsightStatus,
    Recommendation,
    insight_id_for,
)


@dataclass(frozen=True, slots=True)
class ConsolidationConfig:
    min_support: int = 5
    min_outcome_examples: int = 3
    prefer_success_rate: float = 0.60
    avoid_failure_rate: float = 0.60
    min_direction_consistency: float = 0.60
    context_dominance_threshold: float = 0.80
    confidence_threshold: float = 0.60
    target_support_for_full_score: int = 10
    importance_reference_0_1: float = 0.10

    def __post_init__(self) -> None:
        if self.min_support < 2:
            raise ValueError("min_support must be at least 2")
        for name in [
            "prefer_success_rate",
            "avoid_failure_rate",
            "min_direction_consistency",
            "context_dominance_threshold",
            "confidence_threshold",
        ]:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


class Learner:
    """Aggregates immutable post-level Evidence into candidate Insights."""

    CONTEXT_KEYS = ("product_category", "campaign_type", "campaign_goal", "season")

    def __init__(self, config: ConsolidationConfig | None = None):
        self.config = config or ConsolidationConfig()

    @staticmethod
    def _latest_per_post_feature(events: Iterable[EvidenceEvent]) -> list[EvidenceEvent]:
        latest: dict[tuple[str, str, str], EvidenceEvent] = {}
        for event in events:
            key = (event.post_id, event.feature_name, event.observation_window)
            existing = latest.get(key)
            if existing is None or event.observed_at >= existing.observed_at:
                latest[key] = event
        return list(latest.values())

    def consolidate(self, events: Iterable[EvidenceEvent], brand_id: str) -> list[Insight]:
        clean_events = [
            event
            for event in self._latest_per_post_feature(events)
            if event.brand_id == brand_id
        ]
        varying_context_keys = {
            key
            for key in self.CONTEXT_KEYS
            if len(
                {
                    json.dumps(event.context.get(key), ensure_ascii=False, sort_keys=True)
                    for event in clean_events
                    if event.context.get(key) not in (None, "", "Unknown")
                }
            )
            > 1
        }

        grouped: dict[tuple[str, str, str, str], list[EvidenceEvent]] = defaultdict(list)
        for event in clean_events:
            grouped[
                (
                    event.feature_name,
                    event.feature_value_key,
                    event.owner_agent.value,
                    event.feature_role.value,
                )
            ].append(event)

        insights: list[Insight] = []
        for (_, _, _, _), group in grouped.items():
            if len(group) < self.config.min_support:
                continue
            insight = self._build_insight(group, brand_id, varying_context_keys)
            insights.append(insight)

        insights.sort(key=lambda item: item.confidence_0_1, reverse=True)
        return insights

    def _build_insight(
        self,
        group: list[EvidenceEvent],
        brand_id: str,
        varying_context_keys: set[str],
    ) -> Insight:
        first = group[0]
        successes = [event for event in group if event.actual_success]
        failures = [event for event in group if not event.actual_success]
        success_count = len(successes)
        failure_count = len(failures)
        total = len(group)
        success_rate = success_count / total

        positive_rate = (
            sum(
                event.direction == EvidenceDirection.SUPPORTS_SUCCESS
                for event in successes
            )
            / success_count
            if success_count
            else 0.0
        )
        negative_rate = (
            sum(
                event.direction == EvidenceDirection.OPPOSES_SUCCESS
                for event in failures
            )
            / failure_count
            if failure_count
            else 0.0
        )

        if (
            success_count >= self.config.min_outcome_examples
            and success_rate >= self.config.prefer_success_rate
            and positive_rate >= self.config.min_direction_consistency
        ):
            recommendation = Recommendation.PREFER
            outcome_consistency = success_rate
            direction_consistency = positive_rate
        elif (
            failure_count >= self.config.min_outcome_examples
            and (1.0 - success_rate) >= self.config.avoid_failure_rate
            and negative_rate >= self.config.min_direction_consistency
        ):
            recommendation = Recommendation.AVOID
            outcome_consistency = 1.0 - success_rate
            direction_consistency = negative_rate
        else:
            recommendation = Recommendation.MONITOR
            outcome_consistency = max(success_rate, 1.0 - success_rate)
            direction_consistency = max(positive_rate, negative_rate)

        support_score = min(
            total / max(self.config.target_support_for_full_score, self.config.min_support),
            1.0,
        )
        mean_importance = mean(event.importance_0_1 for event in group)
        importance_score = min(
            mean_importance / max(self.config.importance_reference_0_1, 1e-12),
            1.0,
        )
        auc_values = [
            event.model_quality_roc_auc
            for event in group
            if event.model_quality_roc_auc is not None
        ]
        if auc_values:
            mean_auc = mean(auc_values)
            model_score = min(max((mean_auc - 0.5) / 0.5, 0.0), 1.0)
        else:
            model_score = 0.5

        confidence = (
            0.25 * support_score
            + 0.30 * outcome_consistency
            + 0.25 * direction_consistency
            + 0.10 * importance_score
            + 0.10 * model_score
        )
        if not successes or not failures:
            # Success-only/failure-only patterns lack contrast and are deliberately discounted.
            confidence *= 0.85
        confidence = min(max(confidence, 0.0), 1.0)

        mean_support = (
            mean(event.success_support_0_1 for event in successes) if successes else 0.0
        )
        mean_opposition = (
            mean(event.success_opposition_0_1 for event in failures) if failures else 0.0
        )
        context_conditions = self._dominant_context(
            group, first.feature_name, varying_context_keys
        )

        group_key = "|".join(
            [
                brand_id,
                first.owner_agent.value,
                first.feature_name,
                first.feature_value_key,
            ]
        )
        description = self._describe(
            first.feature_name,
            first.feature_value,
            recommendation,
            total,
            success_rate,
            direction_consistency,
            context_conditions,
        )

        return Insight(
            id=insight_id_for(group_key),
            group_key=group_key,
            brand_id=brand_id,
            target_agent=first.owner_agent,
            feature_name=first.feature_name,
            feature_value=first.feature_value,
            feature_role=first.feature_role,
            recommendation=recommendation,
            description=description,
            context_conditions=context_conditions,
            evidence_ids=sorted(event.id for event in group),
            support_count=total,
            success_count=success_count,
            failure_count=failure_count,
            actual_success_rate_0_1=round(success_rate, 10),
            direction_consistency_0_1=round(direction_consistency, 10),
            mean_success_support_0_1=round(mean_support, 10),
            mean_failure_opposition_0_1=round(mean_opposition, 10),
            mean_importance_0_1=round(mean_importance, 10),
            confidence_0_1=round(confidence, 10),
            source_model_versions=sorted({event.model_version for event in group}),
            status=InsightStatus.CANDIDATE,
        )

    def _dominant_context(
        self,
        group: list[EvidenceEvent],
        feature_name: str,
        varying_context_keys: set[str],
    ) -> dict[str, Any]:
        conditions: dict[str, Any] = {}
        for key in self.CONTEXT_KEYS:
            if key == feature_name or key not in varying_context_keys:
                continue
            values = [
                json.dumps(event.context[key], ensure_ascii=False, sort_keys=True)
                for event in group
                if key in event.context and event.context[key] not in (None, "", "Unknown")
            ]
            if not values:
                continue
            value_key, count = Counter(values).most_common(1)[0]
            if count / len(group) >= self.config.context_dominance_threshold:
                conditions[key] = json.loads(value_key)
        return conditions

    @staticmethod
    def _describe(
        feature_name: str,
        value: Any,
        recommendation: Recommendation,
        support_count: int,
        success_rate: float,
        direction_consistency: float,
        conditions: dict[str, Any],
    ) -> str:
        value_text = json.dumps(value, ensure_ascii=False)
        context_text = (
            " under "
            + ", ".join(
                f"{key}={json.dumps(val, ensure_ascii=False)}"
                for key, val in conditions.items()
            )
            if conditions
            else ""
        )
        if recommendation == Recommendation.PREFER:
            action = "is a candidate positive pattern"
        elif recommendation == Recommendation.AVOID:
            action = "is a candidate negative pattern"
        else:
            action = "is not yet consistent enough for a policy"
        return (
            f"{feature_name}={value_text}{context_text} {action}: observed in "
            f"{support_count} posts, with an actual success rate of {success_rate:.0%} "
            f"and SHAP-direction consistency of {direction_consistency:.0%}. "
            "This is associative evidence, not a causal claim."
        )
