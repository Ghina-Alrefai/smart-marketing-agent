from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agents.idea.idea_agent import _ideas_validator
from database.models import Brand, ContentPlan, Product, User
from database.session import SessionLocal
from services import llm_service
from services.llm_service import LLMInvalidJSONError, LLMResponseValidationError
from workflows import campaign_pipeline


class _FakeGemini:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.models = self
        self.calls = 0

    def generate_content(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            text=self._responses.pop(0),
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=20,
            ),
        )


def _fake_tracking(events: list[str]):
    @contextmanager
    def tracker(**_kwargs):
        usage = SimpleNamespace(retry_count=0, set_tokens=lambda **_tokens: None)
        try:
            yield usage
        except Exception as exc:
            events.append(type(exc).__name__)
            raise
        else:
            events.append("success")

    return tracker


def test_json_generation_retries_then_returns_valid_object(monkeypatch) -> None:
    fake = _FakeGemini(['{"posts": [', '{"posts": []}'])
    events: list[str] = []
    monkeypatch.setattr(llm_service, "_client", lambda: fake)
    monkeypatch.setattr(
        llm_service,
        "_generation_config",
        lambda _temperature, *, json_mode: {"json_mode": json_mode},
    )
    monkeypatch.setattr(llm_service, "track_llm_call", _fake_tracking(events))
    monkeypatch.setattr(llm_service.settings, "LLM_JSON_MAX_ATTEMPTS", 2)

    result = llm_service.call_llm_json("return JSON")

    assert result == {"posts": []}
    assert fake.calls == 2
    assert events == ["LLMInvalidJSONError", "success"]


def test_json_generation_never_turns_exhausted_failure_into_empty_dict(
    monkeypatch,
) -> None:
    fake = _FakeGemini(['{"posts": [', '{"posts": ['])
    monkeypatch.setattr(llm_service, "_client", lambda: fake)
    monkeypatch.setattr(
        llm_service,
        "_generation_config",
        lambda _temperature, *, json_mode: {"json_mode": json_mode},
    )
    monkeypatch.setattr(llm_service, "track_llm_call", _fake_tracking([]))
    monkeypatch.setattr(llm_service.settings, "LLM_JSON_MAX_ATTEMPTS", 2)

    with pytest.raises(LLMInvalidJSONError):
        llm_service.call_llm_json("return JSON")


def test_idea_contract_rejects_missing_posts() -> None:
    validate = _ideas_validator(expected_count=2, available_product_ids={1})

    with pytest.raises(LLMResponseValidationError, match="exactly 2 posts"):
        validate({"posts": []})


def test_pipeline_marks_empty_idea_result_as_failed(monkeypatch) -> None:
    suffix = uuid4().hex
    with SessionLocal() as db:
        user = User(name="Pipeline Test", email=f"pipeline-{suffix}@example.test")
        db.add(user)
        db.flush()
        brand = Brand(user_id=user.id, brand_name="Pipeline Brand")
        product = Product(user_id=user.id, title="Pipeline Product")
        db.add_all([brand, product])
        db.flush()
        plan = ContentPlan(
            user_id=user.id,
            brand_id=brand.id,
            campaign_name="Empty Idea Guard",
            days=1,
            product_ids=[product.id],
            campaign_goals=["زيادة المبيعات"],
        )
        db.add(plan)
        db.commit()
        plan_id = plan.id
        product_id = product.id

    from agents.brand import brand_agent
    from agents.idea import idea_agent
    from agents.product import product_analysis_agent
    from agents.strategy import strategy_agent

    monkeypatch.setattr(
        brand_agent,
        "analyze_brand",
        lambda _brand_id: {"_brand": {"brand_name": "Pipeline Brand"}, "tone": "واضح"},
    )
    monkeypatch.setattr(
        campaign_pipeline,
        "get_products",
        lambda _user_id, _product_ids: [
            {"id": product_id, "title": "Pipeline Product", "category": "Test"}
        ],
    )
    monkeypatch.setattr(
        strategy_agent,
        "build_campaign_strategy",
        lambda **_kwargs: {
            "campaign_objective": "زيادة المبيعات",
            "target_audience": "عملاء الاختبار",
            "main_message": "رسالة",
            "content_pillars": ["المنتج"],
            "recommended_post_count": 1,
        },
    )
    monkeypatch.setattr(
        product_analysis_agent,
        "prepare_products_context",
        lambda *_args, **_kwargs: {
            "products": [{"id": product_id, "name": "Pipeline Product"}]
        },
    )
    monkeypatch.setattr(
        idea_agent,
        "generate_post_ideas",
        lambda *_args, **_kwargs: {"posts": []},
    )

    result = campaign_pipeline.run_campaign_pipeline(plan_id)

    assert result.success is False
    assert result.posts_generated == 0
    with SessionLocal() as db:
        stored = db.query(ContentPlan).filter(ContentPlan.id == plan_id).one()
        assert stored.status == "failed"
        assert "لم يولّد وكيل الأفكار أي منشور" in stored.error_message
