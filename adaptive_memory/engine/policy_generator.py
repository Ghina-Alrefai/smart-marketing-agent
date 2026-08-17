from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable

from smart_social_contracts import AgentType, FeatureRole, get_feature_spec

from adaptive_memory.models import (
    Insight,
    InsightStatus,
    Policy,
    PolicyRule,
    PolicyStatus,
    Recommendation,
)


class PolicyGenerator:
    """Creates human-reviewable soft policy drafts from validated Insights."""

    def __init__(self, max_rules_per_agent: int = 8):
        self.max_rules_per_agent = max_rules_per_agent

    def generate(
        self,
        insights: Iterable[Insight],
        *,
        brand_id: str,
        version_for_agent: dict[AgentType, int],
    ) -> list[Policy]:
        grouped: dict[AgentType, list[Insight]] = defaultdict(list)
        for insight in insights:
            if insight.brand_id != brand_id or insight.status != InsightStatus.VALIDATED:
                continue
            grouped[insight.target_agent].append(insight)

        policies: list[Policy] = []
        for agent, agent_insights in grouped.items():
            ranked = sorted(
                agent_insights,
                key=lambda item: (item.confidence_0_1, item.support_count),
                reverse=True,
            )[: self.max_rules_per_agent]
            rules = [self._rule_from_insight(insight) for insight in ranked]
            if not rules:
                continue
            policies.append(
                Policy(
                    brand_id=brand_id,
                    target_agent=agent,
                    version=version_for_agent[agent],
                    rules=rules,
                    source_insight_ids=[insight.id for insight in ranked],
                    status=PolicyStatus.DRAFT,
                    human_approval_required=True,
                )
            )
        return policies

    def _rule_from_insight(self, insight: Insight) -> PolicyRule:
        spec = get_feature_spec(insight.feature_name)
        value_text = self._value_text(insight.feature_value)
        context_clause = self._context_clause(insight.context_conditions)

        if insight.feature_role == FeatureRole.DERIVED:
            if insight.recommendation == Recommendation.PREFER:
                description = (
                    f"Use {spec.label} as a soft ranking signal{context_clause}; favor "
                    "candidates that are closer to the historically successful pattern, "
                    "without copying past posts."
                )
            else:
                description = (
                    f"Use {spec.label} as a warning signal{context_clause}; review "
                    "candidates that strongly resemble the observed weak pattern."
                )
        elif insight.recommendation == Recommendation.PREFER:
            verb = "Test approximately" if isinstance(insight.feature_value, (int, float)) else "Prefer"
            description = (
                f"{verb} {spec.label}={value_text}{context_clause}, provided it remains "
                "compatible with the campaign brief and stable Brand DNA."
            )
        else:
            description = (
                f"Avoid {spec.label}={value_text}{context_clause} unless it is explicitly "
                "required by the campaign brief; use this as a soft recommendation."
            )

        confidence = insight.confidence_0_1
        if confidence >= 0.85:
            priority = 1
        elif confidence >= 0.75:
            priority = 2
        elif confidence >= 0.65:
            priority = 3
        elif confidence >= 0.55:
            priority = 4
        else:
            priority = 5

        return PolicyRule(
            description=description,
            feature_name=insight.feature_name,
            feature_value=insight.feature_value,
            conditions=insight.context_conditions,
            source_insight_id=insight.id,
            confidence_0_1=confidence,
            priority=priority,
            # Adaptive performance policies never become hard guardrails automatically.
            is_hard_constraint=False,
        )

    @staticmethod
    def _value_text(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _context_clause(conditions: dict[str, Any]) -> str:
        if not conditions:
            return ""
        rendered = ", ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in conditions.items()
        )
        return f" when {rendered}"
