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


# ── Campaign architecture (data-driven) ─────────────────────────────────────
def review_campaign_post(post_id: str, content: dict | None = None,
                         design: dict | None = None, brand_guide: dict | None = None) -> dict:
    """
    Review Agent لمعمارية الحملة — مُعطّل حالياً بطلب: يعيد null لكل شيء.
    (البنية جاهزة لتفعيل التقييم لاحقاً دون تغيير الـ pipeline.)
    """
    return {
        "post_id": post_id,
        "approved": None,
        "scores": None,
        "issues": None,
        "suggestions": None,
        "review_summary": None,
    }
