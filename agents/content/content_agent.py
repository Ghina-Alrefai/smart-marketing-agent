"""
Content Agent — Writes hook, caption, CTA, and hashtags.
"""
from __future__ import annotations

import json

from prompts.agent_prompts import CONTENT_GENERATION_PROMPT
from prompts.campaign_prompts import CONTENT_FROM_IDEA_PROMPT
from services.llm_service import call_llm_json


def write_post_content(
    brand_guidelines: str,
    product_analysis: str,
    post_type: str,
    goal: str,
    content_angle: str,
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
        must_use_words=must_use_words,
        forbidden_words=forbidden_words,
        preferred_cta=preferred_cta,
    )
    return call_llm_json(prompt)


# ── Campaign architecture (data-driven, idea-centric) ───────────────────────
def write_content_for_idea(
    idea_post: dict,
    product: dict,
    brand_guide: dict,
    trend: dict | None = None,
    hook_style: str = "الأنسب للفكرة",
    caption_style: str = "متوازن",
) -> dict:
    """
    Content Agent لمعمارية الحملة: يكتب النص النهائي انطلاقاً من الفكرة القانونية
    دون تغيير مفهومها. يعيد {post_id, hook, caption, cta, hashtags}.

    idea_post     : عنصر واحد من مخرَج Idea Agent (فيه post_id, idea{...}, *_direction).
    hook_style    : صيغة الخطّاف المطلوبة لهذا البوست (تدوير عبر بوستات الحملة لتنوّع الأسلوب).
    caption_style : أسلوب/طول الكابشن المطلوب لهذا البوست.
    """
    post_id = idea_post.get("post_id", "")
    prompt = CONTENT_FROM_IDEA_PROMPT.format(
        idea=json.dumps(idea_post.get("idea", {}), ensure_ascii=False),
        product=json.dumps(product, ensure_ascii=False),
        brand_guide=json.dumps(brand_guide, ensure_ascii=False),
        trend=json.dumps(trend or idea_post.get("trend_usage"), ensure_ascii=False),
        hook_direction=idea_post.get("hook_direction", ""),
        cta_direction=idea_post.get("cta_direction", ""),
        hook_style=hook_style,
        caption_style=caption_style,
    )
    # حرارة عالية: الكتابة مهمّة إبداعية
    out = call_llm_json(prompt, temperature=0.85)
    return {
        "post_id": post_id,
        "hook": out.get("hook", ""),
        "caption": out.get("caption", ""),
        "cta": out.get("cta", ""),
        "hashtags": out.get("hashtags", []),
    }
