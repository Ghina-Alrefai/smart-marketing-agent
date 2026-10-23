from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from config import settings
from database.models import (
    Brand,
    ContentPlan,
    GeneratedPost,
    LLMUsageLog,
    Product,
    ScheduledPost,
    User,
)
from database.session import SessionLocal, init_db
from services import campaign_intelligence, llm_service
from workflows.campaign_pipeline import run_campaign_pipeline


def test_offline_demo_uses_prepared_posts_without_any_model_call(monkeypatch) -> None:
    init_db()
    suffix = uuid4().hex
    with SessionLocal() as db:
        user = User(name="Offline Demo", email=f"offline-demo-{suffix}@example.test")
        db.add(user)
        db.flush()
        brand = Brand(user_id=user.id, brand_name="البراق")
        db.add(brand)
        db.flush()
        products = [
            Product(user_id=user.id, title="Galaxy Buds4 R540N"),
            Product(user_id=user.id, title="Samsung Q8FA QLED"),
            Product(user_id=user.id, title="مكيف Samsung AR24CSF"),
            Product(user_id=user.id, title="Family Hub AI Vision RF65DG9H"),
            Product(user_id=user.id, title="Samsung The Freestyle LSP3B"),
            Product(user_id=user.id, title="غسالة الصحون DW60M5070"),
        ]
        db.add_all(products)
        db.flush()
        plan = ContentPlan(
            user_id=user.id,
            brand_id=brand.id,
            campaign_name="Offline Fixture Contract",
            days=3,
            product_ids=[product.id for product in products],
            campaign_goals=["زيادة المبيعات"],
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id

    def forbidden_call(*_args, **_kwargs):
        raise AssertionError("An AI generation function was called in offline demo mode")

    monkeypatch.setattr(settings, "CAMPAIGN_EXECUTION_MODE", "offline_demo")
    monkeypatch.setattr(settings, "CAMPAIGN_DEMO_STEP_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(llm_service, "call_llm_json", forbidden_call)
    monkeypatch.setattr(
        campaign_intelligence,
        "generate_evaluated_post",
        forbidden_call,
    )

    result = run_campaign_pipeline(plan_id)

    assert result.success is True
    assert result.posts_generated == 7

    with SessionLocal() as db:
        stored_plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).one()
        posts = (
            db.query(GeneratedPost)
            .filter(GeneratedPost.content_plan_id == plan_id)
            .order_by(GeneratedPost.day_number)
            .all()
        )
        usage_count = db.query(LLMUsageLog).filter(
            LLMUsageLog.content_plan_id == plan_id
        ).count()
        scheduled_count = db.query(ScheduledPost).join(
            GeneratedPost,
            ScheduledPost.generated_post_id == GeneratedPost.id,
        ).filter(GeneratedPost.content_plan_id == plan_id).count()

        assert stored_plan.days == 7
        assert stored_plan.status == "done"
        assert len(posts) == 7
        assert [post.day_number for post in posts] == list(range(1, 8))
        assert all(post.approved is False for post in posts)
        assert all(post.status == "reviewing" for post in posts)
        assert posts[0].hook.startswith("🎧")
        assert "Galaxy Buds4" in posts[0].caption
        assert posts[4].image_url.endswith("/7.png")
        assert usage_count == 0
        assert scheduled_count == 0

        state = stored_plan.pipeline_state
        nodes = {node["key"]: node for node in state["nodes"]}
        assert state["execution_mode"] == "offline_demo"
        assert state["is_demo"] is True
        assert state["external_ai_calls"] == 0
        assert state["overall_progress"] == 100
        assert nodes["scheduler"]["status"] == "waiting_approval"

        summary = stored_plan.intelligence_summary
        assert summary["data_source"] == "prepared_demo_fixture"
        assert summary["external_ai_calls"] == 0
        assert summary["prediction_available"] is False
        assert summary["human_approval_required"] is True

        campaign = stored_plan.campaign_data["campaign"]
        assert len(campaign["posts"]) == 7
        assert len(campaign["alternate_candidates"]) == 1
        assert campaign["alternate_candidates"][0]["for_post_id"] == "demo_post_002"

    upload_root = Path(settings.UPLOAD_DIR)
    for filename in ("2.jpg", "4.jpg", "5.png", "6.png", "7.png", "8.png", "9.png"):
        assert (upload_root / "demo_campaign" / "alboraq-v1" / filename).is_file()
