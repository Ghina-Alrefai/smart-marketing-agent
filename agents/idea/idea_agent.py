"""
Idea Generation Agent — يولّد الفكرة القانونية لكل بوست.

هذه أهم مرحلة لربط المحتوى بالتصميم: كل بوست له فكرة واحدة (post_id + idea)
تُمرَّر حرفياً لكاتب المحتوى والمصمّم معاً، فلا يخترع أيٌّ منهما مفهوماً مختلفاً.

المدخل (كائنات مهيكلة): strategy + products + brand_guide + trends
المخرَج: {"posts": [{post_id, product_id, content_pillar, content_type, idea{...},
                     hook_direction, cta_direction, trend_usage}, ...]}
"""
from __future__ import annotations

import json

from prompts.campaign_prompts import IDEA_GENERATION_PROMPT
from services.llm_service import call_llm_json


def _ensure_post_ids(posts: list[dict]) -> list[dict]:
    """يضمن أن لكل بوست post_id فريداً وثابتاً (post_001, post_002, ...)."""
    for i, post in enumerate(posts, 1):
        pid = str(post.get("post_id") or "").strip()
        if not pid:
            pid = f"post_{i:03d}"
        post["post_id"] = pid
        # تطبيع idea إلى كائن دائماً
        idea = post.get("idea")
        if isinstance(idea, str):
            post["idea"] = {"concept": idea, "main_message": idea, "visual_direction": ""}
        elif not isinstance(idea, dict):
            post["idea"] = {"concept": "", "main_message": "", "visual_direction": ""}
    return posts


def generate_post_ideas(
    strategy: dict,
    products: list[dict],
    brand_guide: dict,
    trends: list[dict] | None = None,
    post_count: int | None = None,
) -> dict:
    """
    يولّد أفكار المنشورات القانونية للحملة.
      post_count : عدد البوستات (افتراضياً recommended_post_count من الاستراتيجية).
    """
    count = post_count or int(strategy.get("recommended_post_count") or len(products) or 3)
    count = max(1, min(count, 30))

    prompt = IDEA_GENERATION_PROMPT.format(
        strategy=json.dumps(strategy, ensure_ascii=False),
        products=json.dumps(products, ensure_ascii=False, indent=2),
        brand_guide=json.dumps(brand_guide, ensure_ascii=False),
        trends=json.dumps(trends or [], ensure_ascii=False),
        post_count=count,
    )
    # حرارة عالية: توليد الأفكار مهمّة إبداعية تحتاج تنوّعاً
    result = call_llm_json(prompt, temperature=0.9)
    posts = result.get("posts") if isinstance(result, dict) else None
    result = result if isinstance(result, dict) else {}
    result["posts"] = _ensure_post_ids(posts or [])
    return result
