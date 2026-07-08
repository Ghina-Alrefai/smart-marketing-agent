"""
Product Analysis Agent — Derives marketing insights from product data.
"""
from __future__ import annotations

from prompts.agent_prompts import PRODUCT_ANALYSIS_PROMPT
from services.llm_service import call_llm_json
from tools.db_tools import get_product


def analyze_product(product_id: int, brand_guidelines: str) -> dict:
    product = get_product(product_id)
    if not product:
        return {"error": f"Product {product_id} not found"}

    has_image = bool(product.get("image_url"))

    prompt = PRODUCT_ANALYSIS_PROMPT.format(
        title=product["title"],
        description=product["description"] or "",
        price=product["price"] or 0,
        category=product["category"] or "",
        post_count=product.get("post_count", 0),
        brand_guidelines=brand_guidelines,
        has_product_image="true" if has_image else "false",
    )

    return call_llm_json(prompt)
