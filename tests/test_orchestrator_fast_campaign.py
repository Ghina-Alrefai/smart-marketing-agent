from __future__ import annotations

from agents.orchestrator import orchestrator_agent, session_store
from agents.orchestrator.intent_classifier import classify_intent
from services import llm_service


def test_explicit_campaign_launches_without_chat_llm_calls(monkeypatch) -> None:
    def forbidden_llm(*_args, **_kwargs):
        raise AssertionError("explicit campaign must not call Gemini in the chat layer")

    def fake_launch(_session, _user_id, _brand_id, slots, _dry_run):
        return {
            "plan_id": 99,
            "days": slots["days"],
            "status": "started",
        }

    monkeypatch.setattr(llm_service, "call_llm_json", forbidden_llm)
    monkeypatch.setattr(orchestrator_agent, "_launch_campaign", fake_launch)

    session_id = "fast-campaign-test"
    session_store.reset(session_id)
    result = orchestrator_agent.handle_message(
        user_id=10,
        brand_id=20,
        message="أنشئ حملة لمدة 7 أيام",
        session_id=session_id,
        dry_run=False,
    )
    session_store.reset(session_id)

    assert classify_intent("أنشئ حملة لمدة 7 أيام") == ("CREATE_CAMPAIGN", "rule")
    assert result["executed"] == "CREATE_CAMPAIGN"
    assert result["data"] == {"plan_id": 99, "days": 7, "status": "started"}
