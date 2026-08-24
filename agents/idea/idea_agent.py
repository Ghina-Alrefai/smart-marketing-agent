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
from services.llm_service import LLMResponseValidationError, call_llm_json


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
            post["idea"] = {
                "concept": idea,
                "main_message": idea,
                "visual_direction": "",
            }
        elif not isinstance(idea, dict):
            post["idea"] = {"concept": "", "main_message": "", "visual_direction": ""}
    return posts


def _ideas_validator(expected_count: int, available_product_ids: set[int]):
    """Validate and normalize the Idea Agent's complete campaign response."""

    def validate(payload: dict) -> dict:
        posts = payload.get("posts")
        if not isinstance(posts, list):
            raise LLMResponseValidationError("Idea JSON must contain a posts array.")
        if len(posts) != expected_count:
            raise LLMResponseValidationError(
                f"Idea Agent must return exactly {expected_count} posts; got {len(posts)}."
            )
        if not all(isinstance(post, dict) for post in posts):
            raise LLMResponseValidationError("Every generated idea must be an object.")

        normalized = _ensure_post_ids(posts)
        seen_ids: set[str] = set()
        for index, post in enumerate(normalized, 1):
            post_id = str(post.get("post_id") or "").strip()
            if post_id in seen_ids:
                raise LLMResponseValidationError(
                    f"Idea Agent returned duplicate post_id: {post_id}."
                )
            seen_ids.add(post_id)

            try:
                product_id = int(post.get("product_id"))
            except (TypeError, ValueError) as exc:
                raise LLMResponseValidationError(
                    f"Idea {index} has an invalid product_id."
                ) from exc
            if product_id not in available_product_ids:
                raise LLMResponseValidationError(
                    f"Idea {index} references unavailable product_id {product_id}."
                )
            post["product_id"] = product_id

            idea = post.get("idea")
            required_idea_fields = ("concept", "main_message", "visual_direction")
            if not isinstance(idea, dict) or any(
                not isinstance(idea.get(key), str) or not idea[key].strip()
                for key in required_idea_fields
            ):
                raise LLMResponseValidationError(
                    f"Idea {index} must contain non-empty concept, main_message, "
                    "and visual_direction fields."
                )

            for key in (
                "content_pillar",
                "content_type",
                "hook_direction",
                "cta_direction",
            ):
                if not isinstance(post.get(key), str) or not post[key].strip():
                    raise LLMResponseValidationError(
                        f"Idea {index} is missing required field {key}."
                    )

        payload["posts"] = normalized
        return payload

    return validate


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
    count = post_count or int(
        strategy.get("recommended_post_count") or len(products) or 3
    )
    count = max(1, min(count, 30))

    prompt = IDEA_GENERATION_PROMPT.format(
        strategy=json.dumps(strategy, ensure_ascii=False),
        products=json.dumps(products, ensure_ascii=False, indent=2),
        brand_guide=json.dumps(brand_guide, ensure_ascii=False),
        trends=json.dumps(trends or [], ensure_ascii=False),
        post_count=count,
    )
    # حرارة عالية: توليد الأفكار مهمّة إبداعية تحتاج تنوّعاً
    available_product_ids = {int(product["id"]) for product in products}
    return call_llm_json(
        prompt,
        temperature=0.9,
        validator=_ideas_validator(count, available_product_ids),
    )
