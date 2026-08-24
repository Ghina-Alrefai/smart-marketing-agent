from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routers import brands, chat, intelligence, plans, products, scheduled
from api.routers.auth import get_current_user
from database.models import (
    Base,
    Brand,
    ContentPlan,
    LLMUsageLog,
    Product,
    ScheduledPost,
    User,
    utcnow_naive,
)
from database.session import get_db


@pytest.fixture()
def api_context(tmp_path, monkeypatch):
    template_dir = tmp_path / "templates"
    example_dir = tmp_path / "examples"
    product_dir = tmp_path / "products"
    for directory in (template_dir, example_dir, product_dir):
        directory.mkdir()
    monkeypatch.setattr(brands, "TEMPLATES_DIR", template_dir)
    monkeypatch.setattr(brands, "EXAMPLES_DIR", example_dir)
    monkeypatch.setattr(products, "PRODUCTS_DIR", product_dir)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with testing_session() as db:
        owner = User(name="Owner", email="owner@example.test")
        other = User(name="Other", email="other@example.test")
        admin = User(
            name="Admin",
            email="admin@example.test",
            role="super_admin",
            auth_provider="password",
        )
        db.add_all([owner, other, admin])
        db.flush()
        brand = Brand(user_id=owner.id, brand_name="Owner Brand")
        product = Product(user_id=owner.id, title="Owner Product")
        db.add_all([brand, product])
        db.flush()
        plan = ContentPlan(
            user_id=owner.id,
            brand_id=brand.id,
            campaign_name="Owner Plan",
            days=7,
            status="pending",
        )
        scheduled_post = ScheduledPost(
            user_id=owner.id,
            caption="private scheduled post",
            status="scheduled",
        )
        db.add_all([plan, scheduled_post])
        db.commit()
        ids = SimpleNamespace(
            owner=owner.id,
            other=other.id,
            admin=admin.id,
            brand=brand.id,
            product=product.id,
            plan=plan.id,
            scheduled=scheduled_post.id,
        )

    current = {"id": ids.owner}

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    def override_current():
        with testing_session() as db:
            user = db.query(User).filter(User.id == current["id"]).first()
            db.expunge(user)
            return user

    app = FastAPI()
    for router in (
        brands.router,
        products.router,
        plans.router,
        scheduled.router,
        intelligence.router,
        chat.router,
    ):
        app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            current=current,
            ids=ids,
            sessions=testing_session,
        )


def test_static_user_routes_are_not_shadowed_by_id_routes(api_context) -> None:
    ctx = api_context
    products_response = ctx.client.get(f"/api/v1/products/user/{ctx.ids.owner}")
    plans_response = ctx.client.get(f"/api/v1/plans/user/{ctx.ids.owner}")

    assert products_response.status_code == 200
    assert [item["id"] for item in products_response.json()] == [ctx.ids.product]
    assert plans_response.status_code == 200
    assert [item["id"] for item in plans_response.json()] == [ctx.ids.plan]


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/brands/{brand}"),
        ("get", "/api/v1/products/{product}"),
        ("get", "/api/v1/plans/{plan}"),
        ("get", "/api/v1/intelligence/brands/{brand}/status"),
        ("delete", "/api/v1/scheduled/{scheduled}"),
    ],
)
def test_other_user_cannot_access_or_mutate_owned_resources(
    api_context, method: str, path: str
) -> None:
    ctx = api_context
    ctx.current["id"] = ctx.ids.other
    resolved = path.format(**vars(ctx.ids))
    response = getattr(ctx.client, method)(resolved)
    assert response.status_code == 403


def test_super_admin_keeps_cross_account_access(api_context) -> None:
    ctx = api_context
    ctx.current["id"] = ctx.ids.admin
    response = ctx.client.get(f"/api/v1/plans/{ctx.ids.plan}")
    assert response.status_code == 200
    assert response.json()["id"] == ctx.ids.plan


def test_plan_rejects_product_from_another_account(api_context) -> None:
    ctx = api_context
    with ctx.sessions() as db:
        foreign = Product(user_id=ctx.ids.other, title="Foreign Product")
        db.add(foreign)
        db.commit()
        db.refresh(foreign)
        foreign_id = foreign.id

    response = ctx.client.post(
        f"/api/v1/plans/?user_id={ctx.ids.owner}",
        json={
            "brand_id": ctx.ids.brand,
            "days": 7,
            "product_ids": [foreign_id],
        },
    )
    assert response.status_code == 400
    assert str(foreign_id) in response.json()["detail"]


def test_generation_trigger_claims_plan_before_enqueuing(api_context) -> None:
    ctx = api_context
    with ctx.sessions() as db:
        owner = db.query(User).filter(User.id == ctx.ids.owner).first()
        first_tasks = BackgroundTasks()
        first = plans.trigger_generation(ctx.ids.plan, first_tasks, owner, db)
        second_tasks = BackgroundTasks()
        second = plans.trigger_generation(ctx.ids.plan, second_tasks, owner, db)

        db.expire_all()
        stored = db.query(ContentPlan).filter(ContentPlan.id == ctx.ids.plan).first()

    assert first.status == "started"
    assert len(first_tasks.tasks) == 1
    assert second.status == "generating"
    assert len(second_tasks.tasks) == 0
    assert stored.status == "generating"


def test_deleting_campaign_preserves_and_detaches_usage_history(api_context) -> None:
    ctx = api_context
    with ctx.sessions() as db:
        usage = LLMUsageLog(
            trace_id="trace-delete-test",
            span_id="span-delete-test",
            user_id=ctx.ids.owner,
            content_plan_id=ctx.ids.plan,
            agent_name="strategy_agent",
            model_name="gemini-test",
            started_at=utcnow_naive(),
            status="failed",
            error_type="ValidationError",
        )
        db.add(usage)
        db.commit()
        usage_id = usage.id

    response = ctx.client.delete(f"/api/v1/plans/{ctx.ids.plan}")

    assert response.status_code == 204
    with ctx.sessions() as db:
        assert (
            db.query(ContentPlan).filter(ContentPlan.id == ctx.ids.plan).first() is None
        )
        preserved = db.query(LLMUsageLog).filter(LLMUsageLog.id == usage_id).one()
        assert preserved.content_plan_id is None
        assert preserved.status == "failed"


def test_chat_rejects_spoofed_user_and_private_sessions(api_context) -> None:
    ctx = api_context
    ctx.current["id"] = ctx.ids.other
    spoof = ctx.client.post(
        "/api/v1/chat/message",
        json={
            "user_id": ctx.ids.owner,
            "brand_id": ctx.ids.brand,
            "message": "حملة 7 أيام",
            "dry_run": True,
        },
    )
    assert spoof.status_code == 403

    ctx.current["id"] = ctx.ids.owner
    created = ctx.client.post(
        "/api/v1/chat/message",
        json={
            "user_id": ctx.ids.owner,
            "brand_id": ctx.ids.brand,
            "message": "حملة 7 أيام",
            "dry_run": True,
        },
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    ctx.current["id"] = ctx.ids.other
    private = ctx.client.get(f"/api/v1/chat/session/{session_id}")
    assert private.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/brands/{brand}/template",
        "/api/v1/brands/{brand}/examples/image",
        "/api/v1/products/{product}/image",
    ],
)
def test_image_endpoints_reject_html_disguised_as_an_image(
    api_context, path: str
) -> None:
    ctx = api_context
    response = ctx.client.post(
        path.format(**vars(ctx.ids)),
        files={
            "file": (
                "attack.png",
                b"<html><script>alert(1)</script></html>",
                "image/png",
            )
        },
    )
    assert response.status_code == 400


def test_image_upload_is_bounded_and_uses_detected_safe_extension(api_context) -> None:
    ctx = api_context
    oversized = ctx.client.post(
        f"/api/v1/products/{ctx.ids.product}/image",
        files={"file": ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")},
    )
    assert oversized.status_code == 413

    buffer = io.BytesIO()
    Image.new("RGB", (4, 3), color=(12, 34, 56)).save(buffer, format="PNG")
    valid = ctx.client.post(
        f"/api/v1/products/{ctx.ids.product}/image",
        files={"file": ("misleading.html", buffer.getvalue(), "text/html")},
    )
    assert valid.status_code == 200
    assert valid.json()["image_url"].endswith(".png")
