"""
Strategy Agent — Builds the content calendar for the campaign.
"""
from __future__ import annotations

import json

from prompts.agent_prompts import STRATEGY_PLAN_PROMPT
from prompts.campaign_prompts import CAMPAIGN_STRATEGY_PROMPT
from services.llm_service import call_llm_json
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
    return call_llm_json(prompt, temperature=0.3)
