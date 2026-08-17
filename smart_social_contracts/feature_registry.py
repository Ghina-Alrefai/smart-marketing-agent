from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class AgentType(str, Enum):
    CAMPAIGN = "CAMPAIGN_AGENT"
    COPYWRITER = "COPYWRITER_AGENT"
    DESIGNER = "DESIGNER_AGENT"
    SCHEDULER = "SCHEDULER_AGENT"


class FeatureRole(str, Enum):
    """How Adaptive Memory is allowed to use a model feature."""

    CONTROLLABLE = "controllable"
    CONTEXT = "context"
    DERIVED = "derived"
    BRAND_CONSTRAINT = "brand_constraint"


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    owner_agent: AgentType
    role: FeatureRole
    label: str


FEATURE_REGISTRY: dict[str, FeatureSpec] = {
    # Campaign Agent
    "campaign_goal": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTEXT, "campaign goal"),
    "campaign_type": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTROLLABLE, "campaign type"),
    "content_pillar": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTROLLABLE, "content pillar"),
    "product_category": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTEXT, "product category"),
    "brand_name": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTEXT, "brand name"),
    "number_of_products": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTROLLABLE, "number of products"),
    "is_product_post": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTEXT, "product-post type"),
    "season": FeatureSpec(AgentType.CAMPAIGN, FeatureRole.CONTEXT, "season"),

    # Copywriter Agent
    "writing_style": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "writing style"),
    "tone": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "tone"),
    "hook_style": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "hook style"),
    "cta_type": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "CTA type"),
    "cta_presence": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "CTA presence"),
    "number_of_ctas": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "number of CTAs"),
    "dialect": FeatureSpec(AgentType.COPYWRITER, FeatureRole.BRAND_CONSTRAINT, "dialect"),
    "language": FeatureSpec(AgentType.COPYWRITER, FeatureRole.BRAND_CONSTRAINT, "language"),
    "caption_length": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "caption length"),
    "word_count": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "word count"),
    "emoji_count": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "emoji count"),
    "number_of_hashtags": FeatureSpec(AgentType.COPYWRITER, FeatureRole.CONTROLLABLE, "hashtag count"),
    "text_similarity_to_success": FeatureSpec(
        AgentType.COPYWRITER, FeatureRole.DERIVED, "text similarity to successful history"
    ),

    # Designer Agent
    "visual_style": FeatureSpec(AgentType.DESIGNER, FeatureRole.CONTROLLABLE, "visual style"),
    "layout_type": FeatureSpec(AgentType.DESIGNER, FeatureRole.CONTROLLABLE, "layout type"),
    "dominant_colors": FeatureSpec(AgentType.DESIGNER, FeatureRole.BRAND_CONSTRAINT, "dominant colors"),
    "text_in_image": FeatureSpec(AgentType.DESIGNER, FeatureRole.CONTROLLABLE, "text inside image"),
    "contains_human": FeatureSpec(AgentType.DESIGNER, FeatureRole.CONTROLLABLE, "human presence"),
    "logo_position": FeatureSpec(AgentType.DESIGNER, FeatureRole.BRAND_CONSTRAINT, "logo position"),
    "image_count": FeatureSpec(AgentType.DESIGNER, FeatureRole.CONTROLLABLE, "image count"),
    "image_similarity_to_success": FeatureSpec(
        AgentType.DESIGNER, FeatureRole.DERIVED, "image similarity to successful history"
    ),

    # Scheduler Agent
    "day": FeatureSpec(AgentType.SCHEDULER, FeatureRole.CONTROLLABLE, "publishing day"),
    "time_bucket": FeatureSpec(AgentType.SCHEDULER, FeatureRole.CONTROLLABLE, "publishing time bucket"),
}


CONTEXT_FEATURES: frozenset[str] = frozenset(
    {
        "campaign_goal",
        "campaign_type",
        "product_category",
        "brand_name",
        "season",
        "is_product_post",
    }
)


def get_feature_spec(feature_name: str) -> FeatureSpec:
    try:
        return FEATURE_REGISTRY[feature_name]
    except KeyError as exc:
        raise ValueError(
            f"Feature {feature_name!r} is not mapped in the shared feature registry. "
            "Update smart_social_contracts.feature_registry before integrating it."
        ) from exc


def enrich_attribution(attribution: dict[str, Any]) -> dict[str, Any]:
    feature_name = str(attribution["feature"])
    spec = get_feature_spec(feature_name)
    enriched = dict(attribution)
    enriched["owner_agent"] = spec.owner_agent.value
    enriched["feature_role"] = spec.role.value
    return enriched


def enrich_attributions(attributions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_attribution(item) for item in attributions]


def group_attributions_by_agent(
    attributions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {
        agent.value: [] for agent in AgentType
    }
    effects: dict[str, float] = {agent.value: 0.0 for agent in AgentType}
    importance: dict[str, float] = {agent.value: 0.0 for agent in AgentType}

    for item in attributions:
        owner = str(item.get("owner_agent") or get_feature_spec(str(item["feature"])).owner_agent.value)
        grouped.setdefault(owner, []).append(dict(item))
        effects[owner] = effects.get(owner, 0.0) + float(item.get("success_support_0_1") or 0.0)
        importance[owner] = importance.get(owner, 0.0) + float(item.get("importance_0_1") or 0.0)

    for agent_name in grouped:
        grouped[agent_name].sort(
            key=lambda item: float(item.get("importance_0_1") or 0.0), reverse=True
        )

    return {
        "agent_effects": {key: round(value, 10) for key, value in effects.items()},
        "agent_importance": {key: round(value, 10) for key, value in importance.items()},
        "agent_attributions": grouped,
    }
