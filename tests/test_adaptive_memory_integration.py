from __future__ import annotations

import json
from pathlib import Path

from adaptive_memory.adapters import adapt_brand_dna_payload
from adaptive_memory.engine import ConsolidationConfig
from adaptive_memory.models import InsightStatus, PolicyStatus
from adaptive_memory.services import MemoryService
from brand_dna.adaptive_memory import build_runtime_evidence
from brand_dna.paths import project_root
from smart_social_contracts import AgentType, FEATURE_REGISTRY


def _prediction() -> dict:
    root = project_root()
    return json.loads(
        (root / "outputs" / "runtime" / "post3_prediction.json").read_text(
            encoding="utf-8"
        )
    )


def _metrics() -> dict:
    root = project_root()
    return json.loads(
        (root / "examples" / "actual_metrics_success.json").read_text(
            encoding="utf-8"
        )
    )


def test_shared_registry_covers_prediction_features() -> None:
    prediction = _prediction()
    features = {item["feature"] for item in prediction["feature_attributions"]}
    assert features.issubset(FEATURE_REGISTRY)


def test_brand_dna_evidence_contract_and_agent_groups() -> None:
    payload = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
        page_id="al_boraq",
        campaign_id="campaign-test",
    )
    assert payload is not None
    assert payload["schema_version"] == "brand-dna-am-evidence-v1"
    assert payload["actual_success"] is True
    assert payload["context"]["product_category"] == "Mobile"
    assert set(payload["agent_effects"]) == {item.value for item in AgentType}
    assert abs(sum(payload["agent_effects"].values()) - 1.0) < 1e-6
    assert all("owner_agent" in item for item in payload["feature_attributions"])
    assert all("feature_role" in item for item in payload["feature_attributions"])



def test_runtime_event_id_is_stable_across_processing_times() -> None:
    from datetime import datetime, timezone

    first = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
        observation_window="24h",
        observed_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
    )
    second = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
        observation_window="24h",
        observed_at=datetime(2026, 8, 14, 12, 5, tzinfo=timezone.utc),
    )
    assert first is not None and second is not None
    assert first["event_id"] == second["event_id"]
    assert first["observed_at"] != second["observed_at"]

def test_adapter_preserves_shap_semantics_and_numeric_values() -> None:
    payload = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
    )
    assert payload is not None
    _, events = adapt_brand_dna_payload(payload)
    caption = next(item for item in events if item.feature_name == "caption_length")
    assert isinstance(caption.feature_value, float)
    assert caption.importance_0_1 >= 0
    assert "confidence" not in caption.model_dump()


def test_ingestion_is_immutable_and_idempotent(tmp_path: Path) -> None:
    payload = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
    )
    assert payload is not None
    service = MemoryService(db_path=tmp_path / "memory.db")
    first = service.ingest_brand_dna_payload(payload)
    second = service.ingest_brand_dna_payload(payload)
    assert first.inserted_count == first.extracted_count
    assert first.duplicate_count == 0
    assert second.inserted_count == 0
    assert second.duplicate_count == second.extracted_count


def test_one_post_cannot_create_a_policy(tmp_path: Path) -> None:
    payload = build_runtime_evidence(
        _prediction(),
        _metrics(),
        brand_id="al-boraq",
    )
    assert payload is not None
    service = MemoryService(db_path=tmp_path / "memory.db")
    service.ingest_brand_dna_payload(payload)
    result = service.consolidate_insights("al-boraq")
    assert result.candidate_insight_count == 0
    assert service.generate_draft_policies("al-boraq") == []


def test_historical_end_to_end_requires_explicit_activation(tmp_path: Path) -> None:
    root = project_root()
    config = ConsolidationConfig(
        min_support=5,
        min_outcome_examples=3,
        prefer_success_rate=0.60,
        avoid_failure_rate=0.60,
        min_direction_consistency=0.60,
        confidence_threshold=0.60,
    )
    service = MemoryService(
        db_path=tmp_path / "memory.db", consolidation_config=config
    )
    input_path = (
        root / "outputs" / "adaptive_memory" / "all_oof_attributions.jsonl"
    )
    ingestion = service.ingest_jsonl(
        input_path, fallback_brand_id="al-boraq", fallback_page_id="al_boraq"
    )
    assert ingestion["record_count"] == 50
    assert ingestion["inserted_count"] > 1000

    duplicate = service.ingest_jsonl(
        input_path, fallback_brand_id="al-boraq", fallback_page_id="al_boraq"
    )
    assert duplicate["inserted_count"] == 0
    assert duplicate["duplicate_count"] == ingestion["inserted_count"]

    consolidation = service.consolidate_insights("al-boraq")
    assert consolidation.validated_insight_count > 0
    assert consolidation.rejected_insight_count > 0
    validated = service.storage.list_insights(
        brand_id="al-boraq", status=InsightStatus.VALIDATED
    )
    assert validated

    drafts = service.generate_draft_policies("al-boraq")
    assert drafts
    assert all(item.status == PolicyStatus.DRAFT for item in drafts)
    assert service.get_active_policies("al-boraq") == []
    assert all(
        not rule.is_hard_constraint
        for policy in drafts
        for rule in policy.rules
    )

    active = service.activate_policy(drafts[0].id, approved_by="test-reviewer")
    assert active.status == PolicyStatus.ACTIVE
    assert active.approved_by == "test-reviewer"
    assert len(service.get_active_policies("al-boraq", active.target_agent)) == 1

    first_rule = active.rules[0]
    context = service.get_agent_policy_context(
        "al-boraq", active.target_agent, first_rule.conditions
    )
    assert context["rules"]
