"""
Brand Agent — Analyzes brand identity and builds Brand Guidelines.
"""
from __future__ import annotations

from prompts.agent_prompts import BRAND_ANALYSIS_PROMPT
from services.llm_service import call_llm_json
from tools.db_tools import get_brand, get_brand_examples


def analyze_brand(brand_id: int) -> dict:
    """
    Fetch brand data + examples, call LLM to produce Brand Guidelines.
    Returns the guidelines dict (also stored in session by orchestrator).
    """
    brand = get_brand(brand_id)
    if not brand:
        return {"error": f"Brand {brand_id} not found"}

    examples = get_brand_examples(brand_id)
    examples_text = "\n".join(
        f"- [{e['example_type']}]: {e['content']}" for e in examples
    ) or "لا توجد أمثلة"

    prompt = BRAND_ANALYSIS_PROMPT.format(
        brand_name=brand["brand_name"],
        business_description=brand["business_description"] or "",
        tone_of_voice=brand["tone_of_voice"] or "",
        content_style=brand["content_style"] or "",
        visual_style=brand["visual_style"] or "",
        brand_colors=", ".join(brand["brand_colors"]),
        target_audience=brand["target_audience"] or "",
        must_use_words=", ".join(brand["must_use_words"]),
        forbidden_words=", ".join(brand["forbidden_words"]),
        contact_info=brand.get("contact_info") or "غير محدد",
        logo_position=brand.get("logo_position") or "bottom-left",
        examples=examples_text,
    )

    guidelines = call_llm_json(prompt)
    guidelines["_brand"] = brand
    return guidelines
