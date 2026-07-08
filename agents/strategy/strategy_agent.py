"""
Strategy Agent — Builds the content calendar for the campaign.
"""
from __future__ import annotations

import json

from prompts.agent_prompts import STRATEGY_PLAN_PROMPT
from services.llm_service import call_llm_json
from tools.db_tools import get_products


def build_content_strategy(
    brand_guidelines: str,
    user_id: int,
    days: int,
    platform: str,
    campaign_goal: str,
) -> dict:
    """
    Given brand guidelines and campaign parameters, produce a day-by-day strategy.
    brand_guidelines: JSON string of the guidelines dict from brand_agent.
    """
    products = get_products(user_id)
    if not products:
        return {"error": "No products found for this user."}

    products_text = json.dumps(products, ensure_ascii=False, indent=2)

    prompt = STRATEGY_PLAN_PROMPT.format(
        brand_guidelines=brand_guidelines,
        products=products_text,
        days=days,
        platform=platform,
        campaign_goal=campaign_goal,
    )

    return call_llm_json(prompt)
