"""
Content Generation Pipeline.

Orchestrates the full multi-agent flow:
  Brand → Strategy → [Product Analysis → Content → Design → Review] × N days

This module is intentionally framework-agnostic so it can be called
from a FastAPI background task, a CLI, or ADK directly.
"""
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.brand.brand_agent import analyze_brand
from agents.strategy.strategy_agent import build_content_strategy
from agents.product.product_analysis_agent import analyze_product
from agents.content.content_agent import write_post_content
from agents.design.design_agent import create_design
from agents.review.review_agent import review_post
from tools.db_tools import (
    get_brand,
    update_plan_status,
    save_generated_post,
    increment_product_post_count,
)
from database.session import SessionLocal
from database.models import ContentPlan


# ── Progress callback type ─────────────────────────────────────────────────

ProgressCallback = Callable[[str, int, int], None]   # (message, current, total)


@dataclass
class PipelineResult:
    success: bool
    plan_id: int
    posts_generated: int = 0
    errors: list[str] = field(default_factory=list)


# ── Main pipeline ──────────────────────────────────────────────────────────

def run_content_generation_pipeline(
    plan_id: int,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """
    Full pipeline: Brand → Strategy → per-day (Product + Content + Design + Review).
    Persists every generated post to the database.
    """

    def emit(msg: str, current: int = 0, total: int = 0) -> None:
        if on_progress:
            on_progress(msg, current, total)
        print(f"[Pipeline] {msg} ({current}/{total})")

    # ── 1. Load the content plan ──────────────────────────────────────────
    with SessionLocal() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan:
            return PipelineResult(success=False, plan_id=plan_id, errors=["Plan not found"])

        plan_data = {
            "id": plan.id,
            "user_id": plan.user_id,
            "brand_id": plan.brand_id,
            "days": plan.days,
            "campaign_goal": plan.campaign_goal or "زيادة المبيعات",
        }

    update_plan_status(plan_id, "generating")

    errors: list[str] = []

    # ── 2. Brand Analysis ──────────────────────────────────────────────────
    emit("🔍 جاري تحليل هوية البراند...", 1, 5)
    brand_guidelines = analyze_brand(plan_data["brand_id"])
    if "error" in brand_guidelines:
        update_plan_status(plan_id, "failed")
        return PipelineResult(success=False, plan_id=plan_id, errors=[brand_guidelines["error"]])

    brand_info = brand_guidelines.get("_brand", {})
    guidelines_str = json.dumps(brand_guidelines, ensure_ascii=False)

    # ── 3. Content Strategy ────────────────────────────────────────────────
    emit("📋 جاري بناء الاستراتيجية...", 2, 5)
    strategy = build_content_strategy(
        brand_guidelines=guidelines_str,
        user_id=plan_data["user_id"],
        days=plan_data["days"],
        campaign_goal=plan_data["campaign_goal"],
    )
    if "error" in strategy:
        update_plan_status(plan_id, "failed")
        return PipelineResult(success=False, plan_id=plan_id, errors=[strategy["error"]])

    day_plans: list[dict[str, Any]] = strategy.get("days", [])
    total_days = len(day_plans)
    posts_generated = 0

    # ── 4. Per-day generation loop ─────────────────────────────────────────
    for day_plan in day_plans:
        day_num = day_plan.get("day", 0)
        post_type = day_plan.get("post_type", "promotional")
        goal = day_plan.get("goal", "")
        content_angle = day_plan.get("content_angle", "")
        product_id = day_plan.get("recommended_product_id")

        emit(f"✍️ اليوم {day_num}: كتابة المحتوى...", day_num, total_days)

        try:
            # 4a. Product Analysis
            product_analysis: dict = {}
            if product_id:
                product_analysis = analyze_product(
                    product_id=product_id,
                    brand_guidelines=guidelines_str,
                )

            product_analysis_str = json.dumps(product_analysis, ensure_ascii=False)

            # 4b. Content Generation
            content = write_post_content(
                brand_guidelines=guidelines_str,
                product_analysis=product_analysis_str,
                post_type=post_type,
                goal=goal,
                content_angle=content_angle,
                must_use_words=", ".join(brand_info.get("must_use_words", [])),
                forbidden_words=", ".join(brand_info.get("forbidden_words", [])),
                preferred_cta=brand_info.get("preferred_cta", ""),
            )

            hook = content.get("hook", "")
            caption = content.get("caption", "")
            cta = content.get("cta", "")
            hashtags = content.get("hashtags", [])

            emit(f"🎨 اليوم {day_num}: تصميم الصورة...", day_num, total_days)

            # Get product image url if available
            product_image_url = ""
            if product_id:
                from tools.db_tools import get_product as _get_product
                _p = _get_product(product_id)
                product_image_url = _p.get("image_url", "") or ""

            # 4c. Design & Image Generation + Template Overlay
            design = create_design(
                brand_name=brand_info.get("brand_name", ""),
                brand_colors=", ".join(brand_info.get("brand_colors", [])),
                visual_style=brand_info.get("visual_style", "modern"),
                design_mood=product_analysis.get("suggested_design_mood", "modern clean"),
                template_url=brand_info.get("template_url", ""),
                product_info=product_analysis_str,
                product_image_url=product_image_url,
                post_type=post_type,
            )

            image_prompt = design.get("image_prompt", "")
            image_url = design.get("image_url", "")

            emit(f"🔎 اليوم {day_num}: مراجعة الجودة...", day_num, total_days)

            # 4e. Review
            review = review_post(
                brand_guidelines=guidelines_str,
                hook=hook,
                caption=caption,
                cta=cta,
                hashtags=json.dumps(hashtags, ensure_ascii=False),
                image_prompt=image_prompt,
            )

            approved = review.get("approved", False)
            review_notes = review.get("review_summary", "")

            # 4e. Persist
            save_generated_post(
                content_plan_id=plan_id,
                product_id=product_id,
                day_number=day_num,
                post_type=post_type,
                post_goal=goal,
                hook=hook,
                caption=caption,
                cta=cta,
                hashtags=hashtags,
                image_prompt=image_prompt,
                image_url=image_url,
                review_notes=review_notes,
                approved=approved,
            )

            # 4f. Increment product post counter
            if product_id:
                increment_product_post_count(product_id)

            posts_generated += 1

        except Exception as exc:  # noqa: BLE001
            msg = f"Day {day_num} failed: {exc}"
            errors.append(msg)
            print(f"[Pipeline] ERROR — {msg}")

    final_status = "done" if not errors else "done_with_errors"
    update_plan_status(plan_id, final_status)
    emit(" اكتمل التوليد!", total_days, total_days)

    return PipelineResult(
        success=True,
        plan_id=plan_id,
        posts_generated=posts_generated,
        errors=errors,
    )
