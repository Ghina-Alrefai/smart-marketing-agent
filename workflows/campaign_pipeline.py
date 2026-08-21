"""
Campaign Pipeline — المعمارية المهيكلة القائمة على البيانات (Data-driven).

التدفق التسلسلي الواعي بالسياق:

    Orchestrator → Campaign Configuration
        → Brand Agent (Brand Guide)
        → Strategy Agent (استراتيجية كلّية مهيكلة)
        → Product Agent (سياق المنتجات)
        → Idea Agent (فكرة قانونية واحدة لكل بوست: post_id + idea)
        → لكل بوست: ثلاثة مرشحين → تحقق/إصلاح → Brand-DNA أو Cold Start
                       → المرشح الموصى به → تصميم → تقييم → مراجعة بشرية
        → كائن الحملة الموحّد + حفظ
        → البوستات المعتمدة → Schedule Agent

الثابت الأهم:
    فكرة واحدة → مخرَج محتوى واحد + مخرَج تصميم واحد → مراجعة واحدة،
    مع الحفاظ على post_id ثابت عبر كل المراحل.

هذا هو مسار توليد الحملة الوحيد في النظام (استُبدل به الـ pipeline القديم).
"""
from __future__ import annotations

import contextvars
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from database.session import SessionLocal
from database.models import ContentPlan
from monitoring.usage_tracker import trace_context, agent_context
from tools.db_tools import (
    get_products,
    update_plan_generation_state,
    save_campaign_post,
    save_plan_campaign_data,
    increment_product_post_count,
)

ProgressCallback = Callable[[str, int, int], None]
logger = logging.getLogger("smartsocial.campaign")

# ── بنوك الأساليب الدوّارة (تنوّع مفروض عبر بوستات الحملة) ────────────────────
# تُوزَّع بالتناوب حسب ترتيب البوست، فلا يتكرّر نفس الأسلوب في بوستين متتاليين.
_HOOK_STYLES = ["سؤال صادم", "رقم/إحصائية", "تناقض مفاجئ",
                "قصة مصغّرة", "قبل/بعد", "شهادة/اقتباس"]
_CAPTION_STYLES = ["قصير ومباشر (سطران)", "سردي أطول (فقرة قصصية)", "قائمة نقاط سريعة"]
_PHOTO_STYLES = ["لقطة قريبة macro تُبرز التفاصيل",
                 "مشهد lifestyle في سياق الاستخدام اليومي",
                 "flat-lay من الأعلى بترتيب أنيق",
                 "إضاءة درامية بخلفية داكنة",
                 "خلفية بلون واحد نظيف (studio)"]


@dataclass
class CampaignConfig:
    """إعداد الحملة المهيكل — المدخل الوحيد للـ pipeline."""
    user_id: int
    brand_id: int
    days: int = 7
    product_ids: list[int] = field(default_factory=list)   # فارغ = كل المنتجات
    goals: list[str] = field(default_factory=list)
    include_trends: bool = False
    selected_trends: list[dict] = field(default_factory=list)
    selected_events: list[dict] = field(default_factory=list)
    start_date: datetime | None = None


@dataclass
class CampaignResult:
    success: bool
    plan_id: int
    posts_generated: int = 0
    campaign: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# ── بناء Brand Guide موحّد من مخرَج Brand Agent ──────────────────────────────
def _build_brand_guide(analyze_out: dict) -> dict:
    """يدمج بيانات البراند الخام (_brand) مع Brand Guidelines في كائن واحد."""
    brand_info = analyze_out.get("_brand", {}) or {}
    guide = dict(brand_info)                    # brand_name, brand_colors, visual_style, template_url, ...
    guide["guidelines"] = {k: v for k, v in analyze_out.items() if k != "_brand"}
    return guide


# ── أدوات الوضع التجريبي (dry_run) — بلا LLM/صور ─────────────────────────────
def _stub_strategy(days: int, products: list[dict], goals: list[str]) -> dict:
    return {
        "campaign_objective": (goals[0] if goals else "زيادة المبيعات"),
        "target_audience": "(تجريبي) الجمهور المستهدف",
        "main_message": "(تجريبي) الرسالة المحورية",
        "content_pillars": ["ميزات المنتج", "قيمة للعميل"],
        "recommended_content_types": ["Single Image", "Carousel"],
        "recommended_post_count": min(max(len(products), 1), days),
        "product_distribution": [{"product_id": p["id"], "posts": 1} for p in products],
        "kpis": ["الوصول", "التفاعل"],
    }


def _stub_ideas(products: list[dict], count: int) -> dict:
    posts = []
    for i in range(1, count + 1):
        prod = products[(i - 1) % len(products)] if products else {"id": None}
        posts.append({
            "post_id": f"post_{i:03d}",
            "product_id": prod.get("id"),
            "content_pillar": "ميزات المنتج",
            "content_type": "Single Image",
            "idea": {
                "concept": f"(تجريبي) فكرة البوست {i}",
                "main_message": f"(تجريبي) رسالة البوست {i}",
                "visual_direction": "(تجريبي) توجيه بصري متّسق مع الرسالة",
            },
            "hook_direction": "(تجريبي) اتجاه الخطّاف",
            "cta_direction": "(تجريبي) اتجاه CTA",
            "trend_usage": None,
        })
    return {"posts": posts}


# ── الـ pipeline الرئيسي ─────────────────────────────────────────────────────
def run_campaign_pipeline(
    plan_id: int,
    on_progress: ProgressCallback | None = None,
    dry_run: bool = False,
) -> CampaignResult:
    current_stage = "تهيئة التوليد"

    def emit(msg: str, cur: int = 0, total: int = 0) -> None:
        nonlocal current_stage
        current_stage = msg
        if on_progress:
            on_progress(msg, cur, total)
        update_plan_generation_state(plan_id, current_stage=msg)
        logger.info(
            "campaign.stage plan_id=%s step=%s/%s stage=%s",
            plan_id, cur, total, msg,
        )

    # ── 0. تحميل الإعداد من الخطة ──────────────────────────────────────────
    with SessionLocal() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan:
            return CampaignResult(success=False, plan_id=plan_id, errors=["Plan not found"])
        cfg = CampaignConfig(
            user_id=plan.user_id, brand_id=plan.brand_id, days=plan.days or 7,
            product_ids=list(plan.product_ids or []),
            goals=list(plan.campaign_goals or ([plan.campaign_goal] if plan.campaign_goal else [])),
            include_trends=bool(plan.include_trends),
            selected_trends=list(plan.selected_trends or []),
            selected_events=list(plan.selected_events or []),
            start_date=plan.start_date,
        )

    update_plan_generation_state(
        plan_id,
        status="generating",
        current_stage=current_stage,
        clear_error=True,
    )
    errors: list[str] = []

    # كل حملة = دورة تنفيذ واحدة (Trace) — كل استدعاءات النماذج ضمنها تُسجَّل
    # تحت نفس trace_id في monitoring/usage_tracker لأغراض المراقبة والتكلفة.
    with trace_context(user_id=cfg.user_id, content_plan_id=plan_id):
        try:
            # ── 1. Brand Agent → Brand Guide ─────────────────────────────────────
            emit("🏷️ تحليل هوية البراند...", 1, 6)
            if dry_run:
                brand_guide = {"brand_name": "(تجريبي)", "brand_colors": ["#111"],
                               "visual_style": "modern", "template_url": "",
                               "must_use_words": [], "forbidden_words": [], "preferred_cta": ""}
            else:
                from agents.brand.brand_agent import analyze_brand
                with agent_context("brand_agent"):
                    analyze_out = analyze_brand(cfg.brand_id)
                if "error" in analyze_out:
                    update_plan_status(plan_id, "failed")
                    return CampaignResult(False, plan_id, errors=[analyze_out["error"]])
                brand_guide = _build_brand_guide(analyze_out)
            guidelines_str = json.dumps(brand_guide.get("guidelines", {}), ensure_ascii=False)
    try:
        # ── 1. Brand Agent → Brand Guide ─────────────────────────────────────
        emit("🏷️ تحليل هوية البراند...", 1, 6)
        from agents.brand.brand_agent import analyze_brand
        analyze_out = analyze_brand(cfg.brand_id)
        if "error" in analyze_out:
            message = str(analyze_out["error"])
            logger.error("campaign.brand_analysis_failed plan_id=%s error=%s", plan_id, message)
            update_plan_generation_state(plan_id, status="failed", error_message=message)
            return CampaignResult(False, plan_id, errors=[message])
        brand_guide = _build_brand_guide(analyze_out)
        guidelines_str = json.dumps(brand_guide.get("guidelines", {}), ensure_ascii=False)

        # قائمة منتجات أساسية للاستراتيجية
        basic_products = get_products(cfg.user_id, cfg.product_ids or None)
        if not basic_products:
            update_plan_status(plan_id, "failed")
            return CampaignResult(False, plan_id, errors=["لا توجد منتجات مختارة للحملة."])

            # ── 2. Strategy Agent → استراتيجية كلّية ────────────────────────────
            emit("📋 بناء استراتيجية الحملة...", 2, 6)
            if dry_run:
                strategy = _stub_strategy(cfg.days, basic_products, cfg.goals)
            else:
                from agents.strategy.strategy_agent import build_campaign_strategy
                with agent_context("strategy_agent"):
                    strategy = build_campaign_strategy(
                        brand_guide=brand_guide, products=basic_products, goals=cfg.goals,
                        days=cfg.days, include_trends=cfg.include_trends,
                        trends=cfg.selected_trends, events=cfg.selected_events,
                    )

            # ── 3. Product Agent → سياق المنتجات ────────────────────────────────
            emit("📦 تجهيز سياق المنتجات...", 3, 6)
            if dry_run:
                products_ctx = [{"id": p["id"], "name": p["title"], "price": p.get("price"),
                                 "category": p.get("category", ""), "image_url": p.get("image_url", ""),
                                 "is_marketed": p.get("is_marketed", False), "analysis": {"_stub": True}}
                                for p in basic_products]
            else:
                from agents.product.product_analysis_agent import prepare_products_context
                with agent_context("product_agent"):
                    products_ctx = prepare_products_context(
                        cfg.user_id, cfg.product_ids or [p["id"] for p in basic_products], guidelines_str
                    ).get("products", [])
            product_by_id = {p["id"]: p for p in products_ctx}

            # ── 4. Idea Agent → أفكار قانونية (post_id + idea) ──────────────────
            emit("💡 توليد أفكار المنشورات...", 4, 6)
            post_count = int(strategy.get("recommended_post_count") or len(products_ctx) or cfg.days)
            if dry_run:
                ideas = _stub_ideas(products_ctx, min(post_count, 30))
            else:
                from agents.idea.idea_agent import generate_post_ideas
                with agent_context("idea_agent"):
                    ideas = generate_post_ideas(strategy, products_ctx, brand_guide,
                                                cfg.selected_trends, post_count)
            idea_posts = ideas.get("posts", [])
            total = len(idea_posts)

            # ── 5. لكل بوست: 3 مرشحين → تقييم → تصميم → مراجعة بشرية ────────────
            emit("🧠✍️🎨 توليد المرشحين وتقييمهم وتصميمهم...", 5, 6)
            campaign_posts: list[dict] = []
            prev_visual_concepts: list[str] = []   # يُمرَّر كسياق سلبي لتجنّب تكرار التكوين البصري
            for i, idea_post in enumerate(idea_posts, 1):
                try:
                    post_obj = _build_one_post(i, idea_post, product_by_id, brand_guide,
                                               cfg, plan_id, dry_run, prev_visual_concepts)
                    campaign_posts.append(post_obj)
                    vc = (post_obj.get("design") or {}).get("visual_concept", "")
                    if vc:
                        prev_visual_concepts.append(vc)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{idea_post.get('post_id', i)} failed: {exc}")
                    logger.exception(
                    "campaign.post_generation_failed plan_id=%s post_id=%s error_type=%s",
                    plan_id,
                    idea_post.get("post_id", i),
                    type(exc).__name__,
                )

            # ── 6. كائن الحملة الموحّد + حفظ ────────────────────────────────────
            emit("🧩 تجميع كائن الحملة...", 6, 6)
            campaign = {
                "strategy": strategy,
                "products": products_ctx,
                "posts": campaign_posts,
            }
            intelligence_summary = {
            "workflow_version": "team-workflow+brand-dna-am-1.1.0",
            "brand_status": (analyze_out.get("_intelligence") or {}).get("status"),
            "brand_profile_version": (analyze_out.get("_intelligence") or {}).get("profile_version"),
            "prediction_available": bool((analyze_out.get("_intelligence") or {}).get("prediction_available")),
            "human_approval_required": True,
            "posts_ready_for_human_review": sum(
                1 for item in campaign_posts
                if (item.get("review") or {}).get("status") == "ready_for_human_review"
            ),
        }
        campaign["intelligence_summary"] = intelligence_summary
        save_plan_campaign_data(
            plan_id,
            strategy=strategy,
            campaign_data={"campaign": campaign},
            intelligence_summary=intelligence_summary,
        )

            # ── 7. البوستات المعتمدة فقط → Schedule Agent ───────────────────────
            # المراجعة تُعيد null (غير معتمدة) → لا جدولة تلقائية هنا؛
            # يعتمد المستخدم لاحقاً فتُجدول تلقائياً (feature موجود على الاعتماد).
            _schedule_approved(campaign_posts, cfg, dry_run)

            final_status = "done" if not errors else "done_with_errors"
            update_plan_generation_state(
            plan_id,
            status=final_status,
            error_message=" | ".join(errors) if errors else None,
        )
            emit("✅ اكتملت الحملة!", total, total)
            return CampaignResult(True, plan_id, posts_generated=len(campaign_posts),
                                  campaign={"campaign": campaign}, errors=errors)

        except Exception as exc:  # noqa: BLE001
            detail = str(exc).strip() or "حدث خطأ غير معروف أثناء التوليد."
        visible_error = f"فشل عند مرحلة «{current_stage}»: {type(exc).__name__}: {detail}"
        logger.exception(
            "campaign.generation_failed plan_id=%s stage=%s error_type=%s error=%s",
            plan_id,
            current_stage,
            type(exc).__name__,
            detail[:2000],
        )
        update_plan_generation_state(
            plan_id,
            status="failed",
            current_stage=current_stage,
            error_message=visible_error,
        )
            return CampaignResult(False, plan_id, errors=[visible_error])


# ── بناء بوست واحد عبر طبقة الذكاء الموحدة ──────────────────────────────────
def _build_one_post(index: int, idea_post: dict, product_by_id: dict,
                    brand_guide: dict, cfg: CampaignConfig, plan_id: int,
                    dry_run: bool, prev_visual_concepts: list[str] | None = None) -> dict:
    post_id = idea_post["post_id"]
    product = product_by_id.get(idea_post.get("product_id"), {})
    trend = idea_post.get("trend_usage")

    # أساليب دوّارة حسب ترتيب البوست (تنوّع مفروض بلا حاجة لذاكرة داخل الـ LLM)
    hook_style = _HOOK_STYLES[(index - 1) % len(_HOOK_STYLES)]
    caption_style = _CAPTION_STYLES[(index - 1) % len(_CAPTION_STYLES)]
    photo_style = _PHOTO_STYLES[(index - 1) % len(_PHOTO_STYLES)]
    avoid = (prev_visual_concepts or [])[-3:]   # آخر ٣ تكوينات فقط ككفاية

    if dry_run:
        content = {"post_id": post_id, "hook": f"(stub) خطّاف {index}",
                   "caption": f"(stub) نص {index}", "cta": "اطلب الآن", "hashtags": ["#تجريبي"]}
        design = {"post_id": post_id, "design_prompt": "(stub) prompt",
                  "visual_concept": f"(stub) {photo_style} — {idea_post['idea'].get('visual_direction', '')}",
                  "layout": "single", "text_elements": [], "brand_elements": [], "image": ""}
    else:
        from agents.content.content_agent import write_content_for_idea
        from agents.design.design_agent import design_for_idea

        # ThreadPoolExecutor لا يورّث contextvars تلقائياً للخيوط الفرعية،
        # فنلتقط السياق الحالي (trace/user/plan) ونشغّل الدالة صريحاً ضمنه
        # حتى يبقى تتبّع content_agent مرتبطاً بنفس trace_id للحملة.
        ctx = contextvars.copy_context()

        def _write_content():
            def _call():
                with agent_context("content_agent"):
                    return write_content_for_idea(idea_post, product, brand_guide,
                                                  trend, hook_style, caption_style)
            return ctx.run(_call)

        # تنفيذ متوازٍ — لكن كلاهما يستقبل نفس idea_post (نفس المفهوم)
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_content = ex.submit(_write_content)
            content = f_content.result()
            # التصميم يستخدم النص للاتّساق البصري → ننتظر المحتوى ثم نصمّم
            with agent_context("design_agent"):
                design = design_for_idea(idea_post, content, product, brand_guide,
                                         photo_style, avoid)

    # Review Agent — معطّل (null لكل شيء)
    from agents.review.review_agent import review_campaign_post
    with agent_context("review_agent"):
        review = review_campaign_post(post_id, content, design, brand_guide)
    approved = bool(review.get("approved"))   # None → False
    raw_product_id = idea_post.get("product_id")
    try:
        product_id = int(raw_product_id) if raw_product_id is not None else None
    except (TypeError, ValueError):
        product_id = None
    product = product_by_id.get(product_id, {})
    from services.campaign_intelligence import generate_evaluated_post

    evaluated = generate_evaluated_post(
        index=index,
        idea_post=idea_post,
        product=product,
        brand_guide=brand_guide,
        brand_id=cfg.brand_id,
        campaign_goals=cfg.goals,
        start_date=cfg.start_date,
        dry_run=dry_run,
    )
    content = evaluated["content"]
    design = evaluated["design"]
    review = evaluated["review"]
    intelligence = evaluated["intelligence"]
    approved = False  # قرار الإنسان حصراً؛ لا يفعّله أي نموذج أو سياسة ذاكرة.

    # حفظ صف GeneratedPost (يبقي واجهة الحملة/الاعتماد/الجدولة تعمل)
    save_campaign_post(
        content_plan_id=plan_id, product_id=product_id,
        post_id=post_id, idea=idea_post.get("idea", {}), design=design,
        day_number=index, post_type=idea_post.get("content_type", "Single Image"),
        post_goal=idea_post["idea"].get("main_message", ""),
        hook=content.get("hook", ""), caption=content.get("caption", ""),
        cta=content.get("cta", ""), hashtags=content.get("hashtags", []),
        image_prompt=design.get("design_prompt", ""), image_url=design.get("image", ""),
        review_notes=review.get("review_summary"), approved=approved,
        intelligence=intelligence,
    )
    if product_id and not dry_run:
        increment_product_post_count(product_id)

    return {"post_id": post_id, "idea": idea_post, "content": content,
            "design": design, "review": review,
            "intelligence": {
                "selected_candidate": intelligence.get("selected_candidate"),
                "predesign_score": intelligence.get("predesign_score"),
                "multimodal_score": intelligence.get("multimodal_score"),
                "status": intelligence.get("intelligence_status"),
                "generation_trace_id": intelligence.get("generation_trace_id"),
                "candidate_count": len(intelligence.get("candidate_results") or []),
            }}


# ── جدولة البوستات المعتمدة فقط ──────────────────────────────────────────────
def _schedule_approved(posts: list[dict], cfg: CampaignConfig, dry_run: bool) -> None:
    approved = [p for p in posts if p.get("review", {}).get("approved") is True]
    if not approved or dry_run:
        return
    from agents.scheduling.scheduling_agent import schedule_post
    for p in approved:
        c = p["content"]
        schedule_post(cfg.user_id,
                      {"hook": c.get("hook", ""), "caption": c.get("caption", ""),
                       "cta": c.get("cta", ""), "hashtags": c.get("hashtags", []),
                       "image_url": p["design"].get("image", "")},
                      None, "", dry_run=False)
