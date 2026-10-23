"""Deterministic, disclosed offline campaign used when external AI is disabled.

This module never imports an agent, an LLM client, or image-generation code.
It animates the same observable pipeline contract, then stores a prepared
seven-day AlBoraq fixture for human review. The frontend receives an explicit
``offline_demo`` disclosure in every progress snapshot.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from config import settings
from database.models import ContentPlan, GeneratedPost
from database.session import SessionLocal
from tools.db_tools import get_products, save_campaign_post, save_plan_campaign_data
from workflows.pipeline_progress import CampaignPipelineProgress


ProgressCallback = Callable[[str, int, int], None]
logger = logging.getLogger("smartsocial.campaign.offline_demo")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "demo_assets" / "alboraq" / "campaign.json"
ASSET_SOURCE_DIR = FIXTURE_PATH.parent
ASSET_PUBLIC_DIR = "demo_campaign/alboraq-v1"


def _load_fixture() -> dict[str, Any]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    posts = fixture.get("posts")
    if fixture.get("execution_mode") != "offline_demo":
        raise RuntimeError("ملف العرض لا يصرّح بوضع offline_demo.")
    if not isinstance(posts, list) or len(posts) != 7:
        raise RuntimeError("ملف العرض يجب أن يحتوي سبعة منشورات بالضبط.")
    return fixture


def _copy_demo_assets(fixture: dict[str, Any]) -> dict[str, str]:
    filenames = {
        str(item.get("image") or "")
        for item in [
            *(fixture.get("posts") or []),
            *(fixture.get("alternate_candidates") or []),
        ]
        if item.get("image")
    }
    target_dir = Path(settings.UPLOAD_DIR) / ASSET_PUBLIC_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    urls: dict[str, str] = {}
    for filename in sorted(filenames):
        # The fixture may name files, never paths. This prevents traversal if a
        # local demo file is edited later.
        if Path(filename).name != filename:
            raise RuntimeError(f"اسم أصل عرض غير آمن: {filename}")
        source = ASSET_SOURCE_DIR / filename
        if not source.is_file():
            raise RuntimeError(f"صورة العرض غير موجودة: {filename}")
        target = target_dir / filename
        shutil.copy2(source, target)
        urls[filename] = f"/uploads/{ASSET_PUBLIC_DIR}/{filename}"
    return urls


def _normalise(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("–", "-").split())


def _match_product_id(products: list[dict[str, Any]], terms: list[str]) -> int | None:
    normalised_terms = [_normalise(term) for term in terms if _normalise(term)]
    if not normalised_terms:
        return None
    for product in products:
        haystack = _normalise(
            " ".join(
                str(product.get(key) or "")
                for key in ("title", "description", "category")
            )
        )
        if any(term in haystack for term in normalised_terms):
            return int(product["id"])
    return None


def _pause() -> None:
    delay = max(0.0, min(float(settings.CAMPAIGN_DEMO_STEP_DELAY_SECONDS), 10.0))
    if delay:
        time.sleep(delay)


def run_offline_demo_campaign(
    plan_id: int,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Animate a disclosed pipeline and persist the prepared seven-day result."""
    tracker: CampaignPipelineProgress | None = None
    current_stage = "تهيئة وضع العرض دون اتصال"

    def notify(message: str, current: int = 0, total: int = 0) -> None:
        nonlocal current_stage
        current_stage = message
        if on_progress:
            on_progress(message, current, total)

    try:
        fixture = _load_fixture()
        asset_urls = _copy_demo_assets(fixture)

        with SessionLocal() as db:
            plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
            if not plan:
                return {
                    "success": False,
                    "plan_id": plan_id,
                    "posts_generated": 0,
                    "campaign": {},
                    "errors": ["Plan not found"],
                }
            existing_posts = db.query(GeneratedPost).filter(
                GeneratedPost.content_plan_id == plan_id
            ).count()
            if existing_posts:
                raise RuntimeError(
                    "تحتوي الحملة نتائج سابقة؛ أنشئ حملة جديدة لمنع تكرار بيانات العرض."
                )
            user_id = int(plan.user_id)
            plan.days = 7
            db.commit()

        tracker = CampaignPipelineProgress(
            plan_id,
            execution_mode="offline_demo",
        )
        products = get_products(user_id)

        def stage(
            node_key: str,
            activity: str,
            summary: str,
            *,
            step: int,
        ) -> None:
            notify(activity, step, 6)
            tracker.activate(
                node_key,
                activity,
                current_stage=activity,
                metadata={"execution_mode": "offline_demo", "external_ai_calls": 0},
            )
            _pause()
            tracker.complete(
                node_key,
                summary,
                metadata={"execution_mode": "offline_demo", "external_ai_calls": 0},
            )

        stage(
            "orchestrator",
            "عرض توضيحي: التحقق من بيانات الحملة وتجهيز مسار الوكلاء دون اتصال.",
            "اكتمل تجهيز تسلسل العرض الحتمي دون أي استدعاء خارجي.",
            step=0,
        )
        stage(
            "brand",
            "عرض توضيحي: تحميل سياق وهوية البراق المحضّرة مسبقاً.",
            "سياق الهوية الخاص بالعرض جاهز للمرحلة التالية.",
            step=1,
        )
        stage(
            "strategy",
            "عرض توضيحي: تحميل استراتيجية حملة البراق ذات السبعة أيام.",
            "استراتيجية العرض المحضّرة مسبقاً جاهزة.",
            step=2,
        )
        stage(
            "products",
            "عرض توضيحي: مطابقة منتجات Samsung مع بيانات حساب المستخدم عند توفرها.",
            "اكتملت مطابقة المنتجات دون تعديل بيانات التعلم أو عدادات الأداء.",
            step=3,
        )

        posts = fixture["posts"]
        total_posts = len(posts)
        notify("عرض توضيحي: تجهيز أفكار المنشورات السبعة.", 4, 6)
        tracker.activate(
            "ideas",
            "عرض توضيحي: تجهيز زوايا المحتوى المختلفة من بيانات العرض المحضّرة.",
            current_stage=current_stage,
            metadata={"execution_mode": "offline_demo", "external_ai_calls": 0},
        )
        _pause()
        tracker.set_total_posts(total_posts)
        tracker.complete(
            "ideas",
            "جُهزت سبع زوايا محتوى توضيحية لحملة الأيام السبعة.",
            metadata={"post_count": total_posts, "source": "prepared_demo_fixture"},
        )

        campaign_posts: list[dict[str, Any]] = []
        for index, row in enumerate(posts, 1):
            product_id = _match_product_id(products, list(row.get("product_match_terms") or []))
            post_metadata = {
                "execution_mode": "offline_demo",
                "external_ai_calls": 0,
                "source": "prepared_demo_fixture",
                "post_id": row["post_id"],
            }
            production_steps = (
                ("copywriter", "عرض النص المحضّر مسبقاً لهذا المنشور.", "النص التوضيحي جاهز للمراجعة."),
                ("evaluator", "عرض خطوة التحقق من اتساق النص مع سيناريو البراق.", "اكتملت خطوة التحقق التوضيحية دون ادعاء نتيجة نموذج."),
                ("designer", "ربط المنشور بأصل التصميم المحضّر مسبقاً دون توليد صورة.", "تم ربط صورة العرض المحضّرة بالمنشور."),
                ("quality", "فحص سلامة حقول العرض ووجود الصورة قبل الحفظ.", "اكتمل فحص بنية بيانات العرض وأصبح المنشور جاهزاً للمراجعة البشرية."),
            )
            for node_key, activity, summary in production_steps:
                notify(
                    f"المنشور {index}/{total_posts}: {activity}",
                    5,
                    6,
                )
                tracker.activate(
                    node_key,
                    activity,
                    current_stage=current_stage,
                    post_index=index,
                    total_posts=total_posts,
                    metadata=post_metadata,
                )
                _pause()
                tracker.item_complete(
                    node_key,
                    index,
                    total_posts,
                    summary,
                    metadata=post_metadata,
                )

            image_url = asset_urls[row["image"]]
            idea = {
                "concept": row["post_goal"],
                "main_message": row["post_goal"],
                "content_pillar": row["content_pillar"],
                "visual_direction": row["visual_concept"],
                "source": "prepared_demo_fixture",
            }
            content = {
                "hook": row["hook"],
                "caption": row["caption"],
                "cta": row["cta"],
                "hashtags": row["hashtags"],
            }
            design = {
                "image": image_url,
                "visual_concept": row["visual_concept"],
                "design_prompt": "أصل بصري محضّر مسبقاً لوضع العرض دون اتصال.",
                "source": "prepared_demo_asset",
                "is_generated": False,
            }
            review = {
                "status": "ready_for_human_review",
                "approved": None,
                "review_summary": fixture["disclosure_ar"],
            }
            intelligence = {
                "intelligence_status": "not_evaluated",
                "evaluation": {
                    "execution_mode": "offline_demo",
                    "external_ai_calls": 0,
                    "disclosure": fixture["disclosure_ar"],
                },
                "generation_trace_id": f"offline-demo-{plan_id}-{fixture['version']}",
            }
            save_campaign_post(
                content_plan_id=plan_id,
                product_id=product_id,
                post_id=row["post_id"],
                idea=idea,
                design=design,
                day_number=row["day_number"],
                post_type=row["post_type"],
                post_goal=row["post_goal"],
                hook=row["hook"],
                caption=row["caption"],
                cta=row["cta"],
                hashtags=row["hashtags"],
                image_prompt=design["design_prompt"],
                image_url=image_url,
                review_notes=fixture["disclosure_ar"],
                approved=False,
                intelligence=intelligence,
            )
            campaign_posts.append(
                {
                    "post_id": row["post_id"],
                    "idea": {"post_id": row["post_id"], "product_id": product_id, "idea": idea},
                    "content": content,
                    "design": design,
                    "review": review,
                    "intelligence": {
                        "status": "not_evaluated",
                        "execution_mode": "offline_demo",
                        "external_ai_calls": 0,
                    },
                }
            )
            tracker.post_saved(index, total_posts)

        notify("عرض توضيحي: تجميع نتائج الحملة المحضّرة.", 6, 6)
        tracker.activate(
            "assembler",
            "تجميع المنشورات والصور وسجل الإفصاح في كائن حملة واحد.",
            current_stage=current_stage,
            metadata={"execution_mode": "offline_demo", "external_ai_calls": 0},
        )
        _pause()

        alternates = []
        for candidate in fixture.get("alternate_candidates") or []:
            prepared = dict(candidate)
            prepared["image_url"] = asset_urls[candidate["image"]]
            prepared["source"] = "prepared_demo_fixture"
            alternates.append(prepared)

        strategy = dict(fixture["strategy"])
        campaign = {
            "strategy": strategy,
            "products": [
                {
                    "name": row.get("product_name"),
                    "product_id": _match_product_id(
                        products,
                        list(row.get("product_match_terms") or []),
                    ),
                }
                for row in posts
                if row.get("product_name")
            ],
            "posts": campaign_posts,
            "alternate_candidates": alternates,
        }
        intelligence_summary = {
            "workflow_version": "offline-demo-workflow-1.0",
            "execution_mode": "offline_demo",
            "fixture_version": fixture["version"],
            "data_source": "prepared_demo_fixture",
            "external_ai_calls": 0,
            "prediction_available": False,
            "human_approval_required": True,
            "posts_ready_for_human_review": total_posts,
            "disclosure": fixture["disclosure_ar"],
        }
        campaign["intelligence_summary"] = intelligence_summary
        save_plan_campaign_data(
            plan_id,
            strategy=strategy,
            campaign_data={"campaign": campaign},
            intelligence_summary=intelligence_summary,
        )
        tracker.complete(
            "assembler",
            "تم حفظ سبعة منشورات عرض، مع مرشح Q8FA البديل، للمراجعة البشرية.",
            metadata={"posts_generated": total_posts, "alternate_candidates": len(alternates)},
        )
        tracker.finish(posts_generated=total_posts, total_posts=total_posts, errors=[])
        notify("✅ اكتمل وضع العرض وأصبحت النتائج المحضّرة جاهزة للمراجعة.", total_posts, total_posts)
        logger.info(
            "campaign.offline_demo_completed plan_id=%s posts=%s external_ai_calls=0",
            plan_id,
            total_posts,
        )
        return {
            "success": True,
            "plan_id": plan_id,
            "posts_generated": total_posts,
            "campaign": {"campaign": campaign},
            "errors": [],
        }
    except Exception as exc:
        message = f"فشل وضع العرض دون اتصال: {type(exc).__name__}: {exc}"
        logger.exception("campaign.offline_demo_failed plan_id=%s", plan_id)
        if tracker:
            tracker.fail(message, current_stage=current_stage)
        return {
            "success": False,
            "plan_id": plan_id,
            "posts_generated": 0,
            "campaign": {},
            "errors": [message],
        }
