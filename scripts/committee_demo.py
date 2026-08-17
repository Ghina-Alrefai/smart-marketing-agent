"""Create an idempotent Cold-Start demo campaign without external AI calls."""
from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'committee_demo.db'}")
os.environ.setdefault("ADAPTIVE_MEMORY_DB", str(ROOT / "outputs/adaptive_memory/committee_demo.db"))

from database.models import Brand, ContentPlan, Product, User  # noqa: E402
from database.session import SessionLocal, init_db  # noqa: E402
from workflows.campaign_pipeline import run_campaign_pipeline  # noqa: E402


def seed() -> int:
    init_db()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "committee-demo@example.local").first()
        if not user:
            user = User(name="Committee Demo", email="committee-demo@example.local")
            db.add(user); db.flush()
        brand = db.query(Brand).filter(
            Brand.user_id == user.id, Brand.brand_name == "صفحة تجريبية جديدة"
        ).first()
        if not brand:
            brand = Brand(
                user_id=user.id,
                brand_name="صفحة تجريبية جديدة",
                business_description="متجر تقني جديد بلا منشورات سابقة",
                tone_of_voice="ودّي، احترافي",
                content_style="مباشر",
                visual_style="نظيف، عصري",
                brand_colors=["#243B6B", "#FFFFFF"],
                target_audience="طلاب وشباب مهتمون بالتقنية",
                must_use_words=["ضمان"],
                forbidden_words=["الأفضل على الإطلاق"],
                preferred_cta="راسلنا للتفاصيل",
            )
            db.add(brand); db.flush()
        product = db.query(Product).filter(
            Product.user_id == user.id, Product.title == "سماعات لاسلكية تجريبية"
        ).first()
        if not product:
            product = Product(
                user_id=user.id,
                title="سماعات لاسلكية تجريبية",
                description="بطارية طويلة وميكروفون للمكالمات",
                price=49.0,
                category="Audio",
            )
            db.add(product); db.flush()
        plan = ContentPlan(
            user_id=user.id,
            brand_id=brand.id,
            campaign_name="عرض اللجنة — Cold Start",
            days=1,
            campaign_goal="زيادة المبيعات",
            campaign_goals=["زيادة المبيعات"],
            product_ids=[product.id],
            mode="campaign",
        )
        db.add(plan); db.commit(); db.refresh(plan)
        return plan.id


def main() -> None:
    plan_id = seed()
    result = run_campaign_pipeline(plan_id, dry_run=True)
    summary = {
        "success": result.success,
        "plan_id": plan_id,
        "posts_generated": result.posts_generated,
        "errors": result.errors,
        "note": "Dry-run: no Gemini request and no fake probability/SHAP.",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
