from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from database.models import Brand, BrandExample, Product, ContentPlan, GeneratedPost
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
            "platforms": b.platforms or [],
            "template_url": b.template_url or "",
        }

def get_brand_examples(brand_id: int) -> list[dict]:
    with _db() as db:
        return [{"example_type": e.example_type, "content": e.content, "image_url": e.image_url}
                for e in db.query(BrandExample).filter(BrandExample.brand_id == brand_id).all()]

def get_products(user_id: int) -> list[dict]:
    with _db() as db:
        return [{"id": p.id, "title": p.title, "description": p.description,
                 "price": p.price, "category": p.category,
                 "image_url": p.image_url, "post_count": p.post_count or 0}
                for p in db.query(Product).filter(Product.user_id == user_id).all()]

def get_product(product_id: int) -> dict:
    with _db() as db:
        p = db.query(Product).filter(Product.id == product_id).first()
        if not p: return {}
        return {"id": p.id, "title": p.title, "description": p.description,
                "price": p.price, "category": p.category,
                "image_url": p.image_url, "post_count": p.post_count or 0}

def increment_product_post_count(product_id: int) -> None:
    with _db() as db:
        p = db.query(Product).filter(Product.id == product_id).first()
        if p:
            p.post_count = (p.post_count or 0) + 1
            db.commit()

def update_plan_status(plan_id: int, status: str) -> bool:
    with _db() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()
        if not plan: return False
        plan.status = status; db.commit(); return True

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
