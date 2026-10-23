from __future__ import annotations

from uuid import uuid4

from database.models import Brand, ContentPlan, Product, User
from database.session import SessionLocal, init_db
from workflows.pipeline_progress import CampaignPipelineProgress


def _create_plan() -> int:
    init_db()
    suffix = uuid4().hex
    with SessionLocal() as db:
        user = User(name="Progress Test", email=f"progress-{suffix}@example.test")
        db.add(user)
        db.flush()
        brand = Brand(user_id=user.id, brand_name="Progress Brand")
        product = Product(user_id=user.id, title="Progress Product")
        db.add_all([brand, product])
        db.flush()
        plan = ContentPlan(
            user_id=user.id,
            brand_id=brand.id,
            campaign_name="Progress Contract",
            product_ids=[product.id],
            campaign_goals=["زيادة المبيعات"],
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan.id


def test_progress_snapshot_survives_every_agent_handoff() -> None:
    plan_id = _create_plan()
    progress = CampaignPipelineProgress(plan_id)

    progress.activate("orchestrator", "تجهيز المدخلات")
    progress.complete("orchestrator", "المدخلات جاهزة")
    progress.activate("brand", "تحليل الهوية")
    progress.complete("brand", "دليل الهوية جاهز")
    progress.set_total_posts(2)

    for index in (1, 2):
        for node in ("copywriter", "evaluator", "designer", "quality"):
            progress.activate(
                node,
                f"معالجة المنشور {index}",
                post_index=index,
                total_posts=2,
            )
            progress.item_complete(
                node,
                index,
                2,
                f"اكتملت مرحلة {node} للمنشور {index}",
            )
        progress.post_saved(index, 2)

    progress.activate("assembler", "تجميع الحملة")
    progress.complete("assembler", "الحملة مجمعة")
    progress.finish(posts_generated=2, total_posts=2, errors=[])

    with SessionLocal() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).one()
        state = plan.pipeline_state

    nodes = {node["key"]: node for node in state["nodes"]}
    assert state["status"] == "done"
    assert state["overall_progress"] == 100
    assert state["posts_generated"] == 2
    assert state["active_node"] is None
    assert nodes["copywriter"]["completed_items"] == 2
    assert nodes["designer"]["completed_items"] == 2
    assert nodes["scheduler"]["status"] == "waiting_approval"
    assert state["events"][-1]["status"] == "waiting_approval"


def test_failure_is_attached_to_the_agent_that_was_running() -> None:
    plan_id = _create_plan()
    progress = CampaignPipelineProgress(plan_id)
    progress.activate("designer", "توليد الصورة", post_index=1, total_posts=1)
    progress.fail("تعذّر توليد الصورة", current_stage="توليد التصميم")

    with SessionLocal() as db:
        plan = db.query(ContentPlan).filter(ContentPlan.id == plan_id).one()
        state = plan.pipeline_state

    nodes = {node["key"]: node for node in state["nodes"]}
    assert plan.status == "failed"
    assert state["status"] == "failed"
    assert nodes["designer"]["status"] == "failed"
    assert state["events"][-1]["node_key"] == "designer"
    assert "تعذّر توليد الصورة" in state["events"][-1]["detail"]
