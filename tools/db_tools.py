from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from database.models import Brand, BrandExample, Product, ContentPlan, GeneratedPost, ScheduledPost
from database.session import SessionLocal

def _db(): return SessionLocal()

def get_brand(brand_id: int) -> dict[str, Any]:
    with _db() as db:
        b = db.query(Brand).filter(Brand.id == brand_id).first()
        if not b: return {}
        return {
            "id": b.id, "brand_name": b.brand_name,
            "business_description": b.business_description,
            "tone_of_voice": b.tone_of_voice, "content_style": b.content_style,
            "visual_style": b.visual_style, "brand_colors": b.brand_colors or [],
            "target_audience": b.target_audience, "language": b.language,
            "must_use_words": b.must_use_words or [],
            "forbidden_words": b.forbidden_words or [],
            "preferred_cta": b.preferred_cta,
            "preferred_content_types": b.preferred_content_types or [],
            "template_url": b.template_url or "",
        }

def get_brand_examples(brand_id: int) -> list[dict]:
    with _db() as db:
        return [{"example_type": e.example_type, "content": e.content, "image_url": e.image_url}
                for e in db.query(BrandExample).filter(BrandExample.brand_id == brand_id).all()]

def _product_dict(p: Product) -> dict:
    return {"id": p.id, "title": p.title, "description": p.description,
            "price": p.price, "category": p.category,
            "image_url": p.image_url, "image_urls": p.image_urls or [],
            "source_url": p.source_url, "post_count": p.post_count or 0,
            "is_marketed": bool(p.is_marketed)}

def get_products(user_id: int, product_ids: list[int] | None = None) -> list[dict]:
    """كل منتجات المستخدم، أو المُحدّدة فقط إن مُرّرت product_ids."""
    with _db() as db:
        q = db.query(Product).filter(Product.user_id == user_id)
        if product_ids:
            q = q.filter(Product.id.in_(product_ids))
        return [_product_dict(p) for p in q.all()]

def get_product(product_id: int) -> dict:
    with _db() as db:
        p = db.query(Product).filter(Product.id == product_id).first()
        if not p: return {}
        return _product_dict(p)

def increment_product_post_count(product_id: int) -> None:
    with _db() as db:
        p = db.query(Product).filter(Product.id == product_id).first()
        if p:
            p.post_count = (p.post_count or 0) + 1
            p.is_marketed = True          # صار مُسوّقاً له
            db.commit()

def update_plan_status(plan_id: int, status: str) -> bool:
    with _db() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan: return False
        plan.status = status; db.commit(); return True


def update_plan_generation_state(
    plan_id: int,
    *,
    status: str | None = None,
    current_stage: str | None = None,
    error_message: str | None = None,
    clear_error: bool = False,
) -> bool:
    """Persist observable state for a campaign running outside the request lifecycle."""
    with _db() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan:
            return False
        if status is not None:
            plan.status = status
        if current_stage is not None:
            plan.current_stage = current_stage
        if clear_error:
            plan.error_message = None
        elif error_message is not None:
            plan.error_message = error_message[:4000]
        db.commit()
        return True

def save_generated_post(content_plan_id, product_id, day_number, post_type, post_goal,
                        hook, caption, cta, hashtags, image_prompt,
                        image_url="", review_notes="", approved=False) -> int:
    with _db() as db:
        post = GeneratedPost(
            content_plan_id=content_plan_id, product_id=product_id,
            day_number=day_number, post_type=post_type, post_goal=post_goal,
            hook=hook, caption=caption, cta=cta, hashtags=hashtags,
            image_prompt=image_prompt, image_url=image_url,
            review_notes=review_notes, approved=approved,
            status="reviewing" if not approved else "approved",
        )
        db.add(post); db.commit(); db.refresh(post)
        return post.id


def save_campaign_post(content_plan_id, product_id, post_id, idea, design,
                       day_number, post_type, post_goal,
                       hook, caption, cta, hashtags,
                       image_prompt="", image_url="", review_notes=None,
                       approved=False, intelligence=None) -> int:
    """يحفظ بوست حملة مع الحقول المهيكلة (post_id + idea + design)."""
    with _db() as db:
        intelligence = intelligence or {}
        post = GeneratedPost(
            content_plan_id=content_plan_id, product_id=product_id,
            post_id=post_id, idea=idea or {}, design=design or {},
            day_number=day_number, post_type=post_type, post_goal=post_goal,
            hook=hook, caption=caption, cta=cta, hashtags=hashtags or [],
            image_prompt=image_prompt, image_url=image_url,
            review_notes=review_notes, approved=approved,
            status="approved" if approved else "reviewing",
            candidate_results=intelligence.get("candidate_results") or [],
            selected_candidate=intelligence.get("selected_candidate") or {},
            predesign_score=intelligence.get("predesign_score"),
            multimodal_score=intelligence.get("multimodal_score"),
            intelligence_status=intelligence.get("intelligence_status", "not_evaluated"),
            evaluation=intelligence.get("evaluation") or {},
            dna_profile_version=intelligence.get("dna_profile_version"),
            dna_model_version=intelligence.get("dna_model_version"),
            memory_policy_ids=intelligence.get("memory_policy_ids") or [],
            generation_trace_id=intelligence.get("generation_trace_id"),
        )
        db.add(post); db.commit(); db.refresh(post)
        return post.id


def save_plan_campaign_data(plan_id, strategy=None, campaign_data=None,
                            intelligence_summary=None) -> bool:
    """يخزّن مخرَج الاستراتيجية وكائن الحملة الموحّد على الخطة."""
    with _db() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan:
            return False
        if strategy is not None:
            plan.strategy = strategy
        if campaign_data is not None:
            plan.campaign_data = campaign_data
        if intelligence_summary is not None:
            plan.intelligence_summary = intelligence_summary
        db.commit(); return True


# ── Scheduled posts (قسم «المجدولة») ─────────────────────────────────────────
def create_scheduled_post(user_id, hook, caption, cta, hashtags,
                          image_url="", scheduled_at=None, time_text="",
                          generated_post_id=None) -> int:
    with _db() as db:
        sp = ScheduledPost(
            user_id=user_id, generated_post_id=generated_post_id,
            hook=hook, caption=caption, cta=cta,
            hashtags=hashtags or [], image_url=image_url,
            scheduled_at=scheduled_at, time_text=time_text, status="scheduled",
        )
        db.add(sp); db.commit(); db.refresh(sp)
        return sp.id


def get_scheduled_by_post(generated_post_id: int) -> dict | None:
    """يبحث عن جدولة مرتبطة بمنشور حملة معيّن (لتفادي التكرار)."""
    with _db() as db:
        s = (db.query(ScheduledPost)
             .filter(ScheduledPost.generated_post_id == generated_post_id)
             .first())
        return {"id": s.id} if s else None


def delete_scheduled_by_post(generated_post_id: int) -> bool:
    """يحذف جدولة منشور حملة (عند رفضه بعد اعتماده)."""
    with _db() as db:
        s = (db.query(ScheduledPost)
             .filter(ScheduledPost.generated_post_id == generated_post_id)
             .first())
        if not s:
            return False
        db.delete(s); db.commit(); return True


def update_scheduled_time(scheduled_id: int, scheduled_at, time_text: str = "") -> bool:
    """يعدّل وقت النشر لمنشور مجدول."""
    with _db() as db:
        s = db.query(ScheduledPost).filter(ScheduledPost.id == scheduled_id).first()
        if not s:
            return False
        s.scheduled_at = scheduled_at
        if time_text:
            s.time_text = time_text
        db.commit(); return True


def list_scheduled_posts(user_id: int) -> list[dict]:
    with _db() as db:
        rows = (db.query(ScheduledPost)
                .filter(ScheduledPost.user_id == user_id)
                .order_by(ScheduledPost.scheduled_at.is_(None), ScheduledPost.scheduled_at)
                .all())
        return [{"id": s.id, "hook": s.hook, "caption": s.caption, "cta": s.cta,
                 "hashtags": s.hashtags or [], "image_url": s.image_url,
                 "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
                 "time_text": s.time_text, "status": s.status,
                 "created_at": s.created_at.isoformat() if s.created_at else None}
                for s in rows]


def delete_scheduled_post(scheduled_id: int) -> bool:
    with _db() as db:
        s = db.query(ScheduledPost).filter(ScheduledPost.id == scheduled_id).first()
        if not s:
            return False
        db.delete(s); db.commit(); return True
