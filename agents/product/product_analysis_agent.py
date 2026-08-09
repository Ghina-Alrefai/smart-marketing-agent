"""
Product Analysis Agent — Derives marketing insights from product data.
"""
from __future__ import annotations

from prompts.agent_prompts import PRODUCT_ANALYSIS_PROMPT
from services.llm_service import call_llm_json
from tools.db_tools import get_product, get_products


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


# ── Campaign architecture (data-driven) ─────────────────────────────────────
def prepare_products_context(
    user_id: int,
    product_ids: list[int],
    brand_guidelines: str,
) -> dict:
    """
    Product Agent لمعمارية الحملة: يجهّز سياقاً موثوقاً لكل منتج مختار
    (بيانات المنتج + تحليل تسويقي)، دون كتابة المحتوى النهائي.

    يعيد: {"products": [{id, name, price, category, image_url, is_marketed, analysis}, ...]}
    """
    products = get_products(user_id, product_ids or None)
    enriched: list[dict] = []
    for p in products:
        analysis = analyze_product(product_id=p["id"], brand_guidelines=brand_guidelines)
        enriched.append({
            "id": p["id"],
            "name": p["title"],
            "description": p.get("description") or "",
            "price": p.get("price"),
            "category": p.get("category") or "",
            "image_url": p.get("image_url") or "",
            "is_marketed": p.get("is_marketed", False),
            "analysis": analysis,
        })
    return {"products": enriched}
