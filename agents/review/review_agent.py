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
    Lightweight compatibility review for callers outside the integrated path.

    The main campaign pipeline receives richer model/cold-start evaluation from
    ``services.campaign_intelligence``. This function still performs deterministic
    safety checks and deliberately leaves the final approval to a human.
    """
    content = content or {}
    design = design or {}
    brand_guide = brand_guide or {}
    caption = str(content.get("caption") or "")
    issues: list[str] = []
    if len(caption.strip()) < 20:
        issues.append("النص أقصر من الحد الأدنى المطلوب للمراجعة.")
    forbidden = brand_guide.get("forbidden_words") or \
        (brand_guide.get("hard_constraints") or {}).get("forbidden_terms") or []
    found = [word for word in forbidden if str(word).casefold() in caption.casefold()]
    if found:
        issues.append(f"النص يحتوي كلمات ممنوعة: {', '.join(found)}")
    if design and design.get("post_id") not in (None, "", post_id):
        issues.append("معرف التصميم لا يطابق معرف الفكرة.")
    status = "ready_for_human_review" if not issues else "needs_review"
    return {
        "post_id": post_id,
        "approved": None,
        "status": status,
        "scores": {"deterministic_checks_passed": len(issues) == 0},
        "issues": issues,
        "suggestions": [] if not issues else ["صحّح الملاحظات ثم أعد التقييم."],
        "review_summary": "جاهز لمراجعة الإنسان" if not issues else "بحاجة إلى تعديل",
    }
