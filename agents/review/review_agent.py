"""
Review Agent — QA layer that scores and validates each generated post.
"""
from __future__ import annotations

from prompts.agent_prompts import REVIEW_PROMPT
from services.llm_service import call_llm_json


def review_post(
    brand_guidelines: str,
    hook: str,
    caption: str,
    cta: str,
    hashtags: str,
    image_prompt: str,
) -> dict:
    """
    Review a generated post and return scores + approval decision.
    """
    prompt = REVIEW_PROMPT.format(
        brand_guidelines=brand_guidelines,
        hook=hook,
        caption=caption,
        cta=cta,
        hashtags=hashtags,
        image_prompt=image_prompt,
    )
    return call_llm_json(prompt)
