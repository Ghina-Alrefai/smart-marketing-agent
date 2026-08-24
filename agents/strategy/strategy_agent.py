"""
Strategy Agent — Builds the content calendar for the campaign.
"""

from __future__ import annotations

import json

from prompts.agent_prompts import STRATEGY_PLAN_PROMPT
from prompts.campaign_prompts import CAMPAIGN_STRATEGY_PROMPT
from services.llm_service import LLMResponseValidationError, call_llm_json
from tools.db_tools import get_products


def _format_occasions(events: list[dict] | None) -> str:
    """يحوّل المناسبات المختارة إلى نص مقروء للـ prompt."""
    if not events:
        return "لا توجد مناسبات محدّدة ضمن هذه الفترة."
    lines = []
    for e in events:
        day = e.get("day_offset")
        day_txt = f"اليوم {day}" if day else (e.get("date") or "")
        title = e.get("title", "")
        desc = e.get("description", "")
        lines.append(f"- {day_txt}: {title} — {desc}".rstrip(" —"))
    return "\n".join(lines)


def _campaign_strategy_validator(
    available_product_ids: set[int],
):
    """Build a strict validator for the campaign Strategy Agent contract."""
    required_text = ("campaign_objective", "target_audience", "main_message")
    required_lists = (
        "content_pillars",
        "recommended_content_types",
        "product_distribution",
        "kpis",
    )

    def validate(payload: dict) -> dict:
        missing_text = [
            key
            for key in required_text
            if not isinstance(payload.get(key), str) or not payload[key].strip()
        ]
        missing_lists = [
            key
            for key in required_lists
            if not isinstance(payload.get(key), list) or not payload[key]
        ]
        if missing_text or missing_lists:
            missing = ", ".join(missing_text + missing_lists)
            raise LLMResponseValidationError(
                f"Strategy JSON is missing required non-empty fields: {missing}."
            )

        try:
            count = int(payload.get("recommended_post_count"))
        except (TypeError, ValueError) as exc:
            raise LLMResponseValidationError(
                "Strategy recommended_post_count must be an integer."
            ) from exc
        if not 1 <= count <= 30:
            raise LLMResponseValidationError(
                "Strategy recommended_post_count must be between 1 and 30."
            )
        payload["recommended_post_count"] = count

        normalized_distribution = []
        for item in payload["product_distribution"]:
            if not isinstance(item, dict):
                raise LLMResponseValidationError(
                    "Every product_distribution item must be an object."
                )
            try:
                product_id = int(item.get("product_id"))
                posts = int(item.get("posts"))
            except (TypeError, ValueError) as exc:
                raise LLMResponseValidationError(
                    "Strategy product_distribution contains invalid ids or counts."
                ) from exc
            if product_id not in available_product_ids or posts < 1:
                raise LLMResponseValidationError(
                    "Strategy product_distribution references an unavailable product "
                    "or a non-positive post count."
                )
            item["product_id"] = product_id
            item["posts"] = posts
            normalized_distribution.append(item)
        payload["product_distribution"] = normalized_distribution
        return payload

    return validate


def build_content_strategy(
    brand_guidelines: str,
    user_id: int,
    days: int,
    campaign_goal: str = "",
    campaign_goals: list[str] | None = None,
    product_ids: list[int] | None = None,
    events: list[dict] | None = None,
) -> dict:
    """
    Given brand guidelines and campaign parameters, produce a day-by-day strategy.
      brand_guidelines : JSON string of the guidelines dict from brand_agent.
      campaign_goals   : أهداف متعددة (تُدمج مع campaign_goal إن وُجد).
      product_ids      : المنتجات المختارة (فارغ/None = كل منتجات المستخدم).
      events           : المناسبات المختارة ضمن مدة الحملة.
    """
    products = get_products(user_id, product_ids or None)
    if not products:
        return {"error": "No products found for this user."}

    products_text = json.dumps(products, ensure_ascii=False, indent=2)

    # دمج الأهداف: قائمة الأهداف + الهدف المفرد (توافق خلفي)
    goals = list(campaign_goals or [])
    if campaign_goal and campaign_goal not in goals:
        goals.append(campaign_goal)
    goals_text = "، ".join(goals) if goals else "زيادة المبيعات"

    prompt = STRATEGY_PLAN_PROMPT.format(
        brand_guidelines=brand_guidelines,
        products=products_text,
        days=days,
        campaign_goal=goals_text,
        occasions=_format_occasions(events),
    )

    return call_llm_json(prompt)


# ── Campaign architecture (data-driven) ─────────────────────────────────────
def build_campaign_strategy(
    brand_guide: dict,
    products: list[dict],
    goals: list[str],
    days: int,
    include_trends: bool = False,
    trends: list[dict] | None = None,
    events: list[dict] | None = None,
) -> dict:
    """
    المرحلة الأولى في معمارية الحملة: استراتيجية كلّية مهيكلة (لا منشورات فردية).
    ترجع كائن الاستراتيجية (campaign_objective, content_pillars, product_distribution, ...).
    """
    prompt = CAMPAIGN_STRATEGY_PROMPT.format(
        brand_guide=json.dumps(brand_guide, ensure_ascii=False),
        products=json.dumps(products, ensure_ascii=False, indent=2),
        goals="، ".join(goals) if goals else "زيادة المبيعات",
        days=days,
        include_trends="نعم" if include_trends else "لا",
        trends=json.dumps(trends or [], ensure_ascii=False),
        occasions=_format_occasions(events),
    )
    # حرارة منخفضة: الاستراتيجية مهمّة تحليلية تحتاج دقّة والتزاماً بالبنية
    available_product_ids = {int(product["id"]) for product in products}
    return call_llm_json(
        prompt,
        temperature=0.3,
        validator=_campaign_strategy_validator(available_product_ids),
    )
