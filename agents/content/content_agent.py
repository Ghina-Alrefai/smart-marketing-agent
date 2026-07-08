"""
Content Agent — Writes hook, caption, CTA, and hashtags.
"""
from __future__ import annotations

from prompts.agent_prompts import CONTENT_GENERATION_PROMPT
from services.llm_service import call_llm_json


def write_post_content(
    brand_guidelines: str,
    product_analysis: str,
    post_type: str,
    goal: str,
    content_angle: str,
    platform: str,
    must_use_words: str,
    forbidden_words: str,
    preferred_cta: str,
) -> dict:
    """
    Generate caption, hook, CTA, and hashtags for a single post.
    All brand/product context passed as JSON strings.
    """
    prompt = CONTENT_GENERATION_PROMPT.format(
        brand_guidelines=brand_guidelines,
        product_analysis=product_analysis,
        post_type=post_type,
        goal=goal,
        content_angle=content_angle,
        platform=platform,
        must_use_words=must_use_words,
        forbidden_words=forbidden_words,
        preferred_cta=preferred_cta,
    )
    return call_llm_json(prompt)
