"""One integration path for candidate generation, evaluation, and design.

The existing campaign workflow remains the orchestrator. This module replaces
only the old single-draft content/design branch with the reviewed Brand-DNA
contract: three candidates, strict validation, optional model ranking, bounded
repair, one recommended candidate, design, and a final evaluation trace.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from brand_dna.generation import generate_candidates, generate_design_prompt
from config import settings
from services.brand_intelligence_service import (
    get_brand_context,
    memory_service,
    project_root,
)
from tools.image_generation import generate_image, generate_image_with_product
from tools.template_overlay import apply_brand_template


ARABIC_DAYS = [
    "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"
]


def _season(day: datetime) -> str:
    month = day.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def build_candidate_brief(
    *,
    index: int,
    idea_post: dict[str, Any],
    product: dict[str, Any],
    brand_guide: dict[str, Any],
    campaign_goals: list[str],
    start_date: datetime | None,
) -> dict[str, Any]:
    """Translate the team's idea object into the locked prediction contract."""
    publish_day = (start_date or datetime.utcnow()) + timedelta(days=max(index - 1, 0))
    language = (brand_guide.get("language") or "ar").lower()
    return {
        "campaign_goal": campaign_goals[0] if campaign_goals else "زيادة المبيعات",
        "campaign_type": idea_post.get("content_type") or "Single Image",
        "product_category": product.get("category") or "general",
        "brand_name": brand_guide.get("brand_name") or "Unknown brand",
        "day": ARABIC_DAYS[publish_day.weekday()],
        "time_bucket": "evening",
        "season": _season(publish_day),
        "language": "Arabic" if language.startswith("ar") else language,
        "dialect": "Modern Standard Arabic",
        "is_product_post": "yes" if product else "no",
        "product": {
            "id": product.get("id"),
            "name": product.get("name") or product.get("title") or "",
            "description": product.get("description") or "",
            "price": product.get("price"),
        },
        "approved_idea": idea_post.get("idea") or {},
        "content_pillar": idea_post.get("content_pillar") or "product value",
        "hook_direction": idea_post.get("hook_direction") or "",
        "cta_direction": idea_post.get("cta_direction") or "",
    }


def _stub_candidate(candidate_id: str, brief: dict[str, Any], profile: dict[str, Any], variant: int) -> dict[str, Any]:
    colors = (profile.get("visual_profile") or {}).get("brand_colors") or \
        (profile.get("visual_profile") or {}).get("common_color_families") or ["blue", "white"]
    tones = (profile.get("caption_profile") or {}).get("common_tones") or ["professional"]
    return {
        "id": candidate_id,
        "caption": f"نسخة اختبار تكامل رقم {variant}: رسالة واضحة للمنتج مع فائدة عملية ودعوة مركزة لاتخاذ الإجراء.",
        "campaign_goal": brief["campaign_goal"],
        "campaign_type": brief["campaign_type"],
        "product_category": brief["product_category"],
        "brand_name": brief["brand_name"],
        "day": brief["day"],
        "time_bucket": brief["time_bucket"],
        "season": brief["season"],
        "language": brief["language"],
        "dialect": brief["dialect"],
        "cta_presence": "present",
        "cta_type": "Buy",
        "tone": tones[(variant - 1) % len(tones)],
        "writing_style": ["direct", "feature list", "educational"][variant - 1],
        "hook_type": ["benefit", "question", "announcement"][variant - 1],
        "content_pillar": brief["content_pillar"],
        "number_of_ctas": 1,
        "number_of_hashtags": variant,
        "number_of_products": 1 if brief["is_product_post"] == "yes" else 0,
        "contains_human": "no",
        "dominant_colors": "; ".join(colors),
        "logo_position": "top-right",
        "text_in_image": "فائدة المنتج",
        "visual_style": "clean product hero",
        "layout_type": "centered product",
        "image_count": 1,
        "is_product_post": brief["is_product_post"],
    }


def _dry_generation(brief: dict[str, Any], profile: dict[str, Any], scoring_mode: str) -> dict[str, Any]:
    from brand_dna.generation import rank_candidates_cold_start

    raw = [_stub_candidate(f"dry-candidate-{i}", brief, profile, i) for i in range(1, 4)]
    ranked = rank_candidates_cold_start(raw)
    return {
        "schema_version": "brand-dna-candidate-generation-v2",
        "prompt_version": "dry-run-no-external-model",
        "status": "ready",
        "scoring_mode": "cold_start_rules",
        "prediction_available": False,
        "human_approval_required": True,
        "attempt_count": 1,
        "minimum_predicted_success_probability": None,
        "adaptive_memory_applied": False,
        "adaptive_memory_context": {},
        "candidates": ranked,
        "attempt_history": [{"attempt": 1, "stage": "dry_run", "accepted": True}],
        "warnings": [
            "Dry run uses deterministic fixtures and never claims a model prediction.",
            f"Requested runtime mode was {scoring_mode}.",
        ],
    }


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[0][:240]
    return text.strip()[:240]


def _hashtags(text: str, expected: int) -> list[str]:
    found = list(dict.fromkeys(re.findall(r"#[\w\u0600-\u06ff]+", text)))
    return found[: max(expected, 0)]


def _policy_ids(generation: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for context in (generation.get("adaptive_memory_context") or {}).values():
        for rule in context.get("rules") or []:
            policy_id = rule.get("policy_id")
            if policy_id and policy_id not in ids:
                ids.append(policy_id)
    return ids


def _local_image_path(image_url: str) -> Path | None:
    if not image_url.startswith("/uploads/"):
        return None
    path = Path(settings.UPLOAD_DIR) / image_url.removeprefix("/uploads/")
    return path.resolve() if path.exists() else None


def _create_design(
    selected: dict[str, Any],
    profile: dict[str, Any],
    brand_key: str,
    product: dict[str, Any],
    template_url: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    if dry_run:
        return {
            "post_id": selected.get("id"),
            "design_prompt": "Dry-run design prompt",
            "visual_concept": "اختبار تكامل بلا توليد صورة خارجي",
            "layout": selected.get("layout_type", "single"),
            "text_elements": [selected.get("text_in_image", "")],
            "brand_elements": [selected.get("logo_position", "")],
            "image": "",
            "design_status": "dry_run",
        }

    design_result = generate_design_prompt(
        selected,
        profile,
        memory_service=memory_service(),
        brand_id=brand_key,
        max_attempts=settings.BRAND_DNA_GENERATION_MAX_ATTEMPTS,
        template_applied_externally=bool(template_url and template_url.strip()),
    )
    prompt = design_result.get("image_prompt_en", "")
    notes = design_result.get("designer_notes_ar", "")
    image_url = ""
    if design_result.get("status") == "ready" and prompt:
        product_image = product.get("image_url") or ""
        if product_image:
            inner = generate_image_with_product(
                prompt,
                notes,
                product_image,
                template_applied_externally=bool(template_url and template_url.strip()),
            )
        else:
            inner = generate_image(
                prompt,
                notes,
                template_applied_externally=bool(template_url and template_url.strip()),
            )
        if inner:
            image_url = apply_brand_template(inner, template_url)
    return {
        "post_id": selected.get("id"),
        "design_prompt": prompt,
        "visual_concept": notes,
        "layout": selected.get("layout_type", ""),
        "text_elements": [selected.get("text_in_image", "")],
        "brand_elements": [selected.get("logo_position", "")],
        "image": image_url,
        "design_status": design_result.get("status", "needs_review"),
        "design_trace": design_result,
    }


def generate_evaluated_post(
    *,
    index: int,
    idea_post: dict[str, Any],
    product: dict[str, Any],
    brand_guide: dict[str, Any],
    brand_id: int,
    campaign_goals: list[str],
    start_date: datetime | None,
    dry_run: bool = False,
    include_design: bool = True,
) -> dict[str, Any]:
    """Return content/design plus a complete, reproducible intelligence trace."""
    context = get_brand_context(brand_id)
    if "error" in context:
        raise ValueError(context["error"])
    profile = context["profile"]
    key = context["brand_key"]
    scoring_mode = "brand_dna" if context["prediction_available"] else "cold_start_rules"
    brief = build_candidate_brief(
        index=index,
        idea_post=idea_post,
        product=product,
        brand_guide=brand_guide,
        campaign_goals=campaign_goals,
        start_date=start_date,
    )

    if dry_run:
        generation = _dry_generation(brief, profile, scoring_mode)
    else:
        generation = generate_candidates(
            brief,
            profile,
            memory_service=memory_service(),
            brand_id=key,
            max_attempts=settings.BRAND_DNA_GENERATION_MAX_ATTEMPTS,
            min_success_probability=settings.BRAND_DNA_MIN_CANDIDATE_PROBABILITY,
            root=project_root(),
            scoring_mode=scoring_mode,
        )
    if not generation.get("candidates"):
        raise RuntimeError("No valid candidate survived validation; inspect generation attempt_history.")

    recommended = generation["candidates"][0]
    selected = dict(recommended.get("candidate") or {})
    caption = selected.get("caption", "")
    cta = ""
    if int(selected.get("number_of_ctas") or 0) > 0:
        cta = (profile.get("caption_profile") or {}).get("preferred_cta") or selected.get("cta_type", "")
    content = {
        "post_id": idea_post.get("post_id"),
        "hook": _first_line(caption),
        "caption": caption,
        "cta": cta,
        "hashtags": _hashtags(caption, int(selected.get("number_of_hashtags") or 0)),
    }
    design = (
        _create_design(
            selected,
            profile,
            key,
            product,
            brand_guide.get("template_url", ""),
            dry_run=dry_run,
        )
        if include_design
        else {
            "post_id": selected.get("id"),
            "design_prompt": "",
            "visual_concept": "",
            "layout": selected.get("layout_type", ""),
            "text_elements": [],
            "brand_elements": [],
            "image": "",
            "design_status": "not_requested",
        }
    )

    multimodal = None
    image_path = _local_image_path(design.get("image", ""))
    if include_design and scoring_mode == "brand_dna" and image_path and not dry_run:
        from brand_dna.predictor import predict_candidate

        multimodal_input = {**selected, "image_path": str(image_path)}
        multimodal = predict_candidate(multimodal_input, "multimodal", root=project_root())

    predesign_score = recommended.get("predicted_success_probability")
    cold_score = recommended.get("cold_start_quality_score_0_1")
    multimodal_score = multimodal.get("predicted_success_probability") if multimodal else None
    design_ready = (
        dry_run
        or not include_design
        or (design.get("design_status") == "ready" and bool(design.get("image")))
    )
    passed = generation.get("status") == "ready" and design_ready and (
        multimodal_score is None
        or multimodal_score >= settings.BRAND_DNA_MIN_CANDIDATE_PROBABILITY
    )
    status = "ready_for_human_review" if passed else "needs_review"
    trace_seed = f"{key}:{idea_post.get('post_id')}:{generation.get('prompt_version')}:{selected.get('id')}"
    trace_id = "trace:" + hashlib.sha256(trace_seed.encode("utf-8")).hexdigest()[:20]
    evaluation = {
        "status": status,
        "schema_valid": True,
        "candidate_generation_status": generation.get("status"),
        "design_ready": design_ready,
        "scoring_mode": scoring_mode,
        "prediction_available": context["prediction_available"],
        "predesign_probability": predesign_score,
        "cold_start_quality_score": cold_score,
        "multimodal_probability": multimodal_score,
        "minimum_probability": (
            settings.BRAND_DNA_MIN_CANDIDATE_PROBABILITY
            if context["prediction_available"] else None
        ),
        "human_approval_required": True,
        "warnings": generation.get("warnings") or [],
    }
    if multimodal:
        generation["multimodal_selected_evaluation"] = multimodal

    return {
        "content": content,
        "design": design,
        "review": {
            "post_id": idea_post.get("post_id"),
            "approved": None,
            "status": status,
            "scores": {
                "predesign_probability": predesign_score,
                "cold_start_quality": cold_score,
                "multimodal_probability": multimodal_score,
            },
            "issues": [] if passed else ["تعذر اجتياز إحدى بوابات الجودة؛ يلزم التعديل أو إعادة التوليد."],
            "suggestions": [],
            "review_summary": "جاهز لمراجعة الإنسان" if passed else "بحاجة إلى مراجعة قبل الاعتماد",
        },
        "intelligence": {
            "candidate_results": generation.get("candidates") or [],
            "selected_candidate": selected,
            "predesign_score": predesign_score,
            "multimodal_score": multimodal_score,
            "intelligence_status": status,
            "evaluation": evaluation,
            "dna_profile_version": context.get("profile_version"),
            "dna_model_version": (
                recommended.get("model_version")
                or (multimodal or {}).get("model_version")
            ),
            "memory_policy_ids": _policy_ids(generation),
            "generation_trace_id": trace_id,
            "generation_trace": generation,
            "brief": brief,
        },
    }
