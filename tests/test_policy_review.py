from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adaptive_memory.engine import PolicyReviewConfig
from adaptive_memory.models import (
    Insight,
    InsightStatus,
    Policy,
    PolicyReviewDecision,
    PolicyRule,
    PolicyStatus,
    Recommendation,
)
from adaptive_memory.services import MemoryService
from brand_dna.adaptive_memory import build_runtime_evidence
from brand_dna.paths import project_root
from smart_social_contracts import AgentType, FeatureRole


def _policy(service: MemoryService, *, min_posts: int = 3) -> Policy:
    draft = Policy(
        brand_id="policy-review-brand",
        target_agent=AgentType.COPYWRITER,
        version=1,
        minimum_review_posts=min_posts,
        rules=[
            PolicyRule(
                description="Prefer the validated caption-length pattern.",
                feature_name="caption_length",
                feature_value=100,
                source_insight_id="test-insight",
                confidence_0_1=0.80,
                priority=2,
            )
        ],
    )
    service.storage.save_policy(draft)
    return service.activate_policy(draft.id, approved_by="test-reviewer")


def _prediction() -> dict:
    return json.loads(
        (project_root() / "outputs" / "runtime" / "post3_prediction.json").read_text(
            encoding="utf-8"
        )
    )


def _success_metrics() -> dict:
    return json.loads(
        (project_root() / "examples" / "actual_metrics_success.json").read_text(
            encoding="utf-8"
        )
    )


def _failure_metrics() -> dict:
    return json.loads(
        (project_root() / "examples" / "actual_metrics_failure.json").read_text(
            encoding="utf-8"
        )
    )


def test_activation_sets_a_bounded_monthly_review_schedule(tmp_path: Path) -> None:
    service = MemoryService(
        db_path=tmp_path / "memory.db",
        policy_review_config=PolicyReviewConfig(
            review_interval_days=30,
            review_grace_days=15,
            minimum_evaluated_posts=3,
        ),
    )
    active = _policy(service)

    assert active.status == PolicyStatus.ACTIVE
    assert active.valid_from is not None
    assert active.next_review_at is not None
    assert active.valid_until is not None
    assert active.next_review_at - active.valid_from == timedelta(days=30)
    assert active.valid_until - active.next_review_at == timedelta(days=15)


def test_reviewer_counts_only_explicitly_linked_posts_and_renews(tmp_path: Path) -> None:
    service = MemoryService(
        db_path=tmp_path / "memory.db",
        policy_review_config=PolicyReviewConfig(minimum_evaluated_posts=3),
    )
    active = _policy(service)

    prediction = _prediction()
    for index in range(3):
        post_prediction = dict(prediction)
        post_prediction["post_id"] = f"linked-review-post-{index}"
        payload = build_runtime_evidence(
            post_prediction,
            _success_metrics(),
            brand_id=active.brand_id,
            applied_policy_ids=[active.id],
        )
        assert payload is not None
        service.ingest_brand_dna_payload(payload)

    unlinked_prediction = dict(prediction)
    unlinked_prediction["post_id"] = "unlinked-review-post"
    unlinked = build_runtime_evidence(
        unlinked_prediction,
        _success_metrics(),
        brand_id=active.brand_id,
    )
    assert unlinked is not None
    service.ingest_brand_dna_payload(unlinked)

    review = service.review_policy(
        active.id, reviewed_by="test-reviewer", force=True
    )
    updated = service.storage.get_policy(active.id)

    assert review.decision == PolicyReviewDecision.RENEW
    assert review.evaluated_post_count == 3
    assert review.success_rate_0_1 == 1.0
    assert updated is not None
    assert updated.status == PolicyStatus.ACTIVE
    assert updated.last_review_decision == PolicyReviewDecision.RENEW
    assert service.stats()["policy_reviews"] == 1


def test_insufficient_evidence_defers_then_pauses(tmp_path: Path) -> None:
    service = MemoryService(
        db_path=tmp_path / "memory.db",
        policy_review_config=PolicyReviewConfig(
            minimum_evaluated_posts=3,
            max_insufficient_reviews=1,
        ),
    )
    active = _policy(service)

    first = service.review_policy(active.id, reviewed_by="test-reviewer", force=True)
    after_first = service.storage.get_policy(active.id)
    assert first.decision == PolicyReviewDecision.INSUFFICIENT_EVIDENCE
    assert after_first is not None
    assert after_first.status == PolicyStatus.ACTIVE
    assert after_first.insufficient_review_count == 1

    second = service.review_policy(active.id, reviewed_by="test-reviewer", force=True)
    after_second = service.storage.get_policy(active.id)
    assert second.decision == PolicyReviewDecision.SUSPEND
    assert after_second is not None
    assert after_second.status == PolicyStatus.PAUSED
    assert service.get_active_policies(active.brand_id) == []


def test_policy_expires_when_review_grace_period_elapses(tmp_path: Path) -> None:
    service = MemoryService(
        db_path=tmp_path / "memory.db",
        policy_review_config=PolicyReviewConfig(minimum_evaluated_posts=3),
    )
    active = _policy(service)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    service.storage.update_policy(
        active.model_copy(update={"valid_until": past, "next_review_at": past})
    )

    assert service.get_active_policies(active.brand_id) == []
    expired = service.storage.get_policy(active.id)
    assert expired is not None
    assert expired.status == PolicyStatus.EXPIRED
    assert expired.expiration_reason == "review_grace_period_elapsed"


def test_modify_creates_a_new_draft_version_without_overwriting_history(
    tmp_path: Path,
) -> None:
    service = MemoryService(
        db_path=tmp_path / "memory.db",
        policy_review_config=PolicyReviewConfig(minimum_evaluated_posts=8),
    )
    active = _policy(service, min_posts=8)
    replacement_insight = Insight(
        id="replacement-insight",
        group_key="policy-review-brand|COPYWRITER_AGENT|caption_length|120|{}",
        brand_id=active.brand_id,
        target_agent=AgentType.COPYWRITER,
        feature_name="caption_length",
        feature_value=120,
        feature_role=FeatureRole.CONTROLLABLE,
        recommendation=Recommendation.PREFER,
        description="Recent evidence supports testing a revised caption length.",
        evidence_ids=[f"replacement-evidence-{index}" for index in range(8)],
        support_count=8,
        success_count=4,
        failure_count=4,
        actual_success_rate_0_1=0.50,
        direction_consistency_0_1=0.75,
        mean_success_support_0_1=0.70,
        mean_failure_opposition_0_1=0.65,
        mean_importance_0_1=0.60,
        confidence_0_1=0.70,
        status=InsightStatus.VALIDATED,
    )
    service.storage.save_insight(replacement_insight)

    prediction = _prediction()
    for index in range(8):
        post_prediction = dict(prediction)
        post_prediction["post_id"] = f"modify-review-post-{index}"
        payload = build_runtime_evidence(
            post_prediction,
            _success_metrics() if index < 4 else _failure_metrics(),
            brand_id=active.brand_id,
            applied_policy_ids=[active.id],
        )
        assert payload is not None
        service.ingest_brand_dna_payload(payload)

    review = service.policy_reviewer.review_policy(
        active.id,
        reviewed_by="test-reviewer",
        force=True,
    )
    old = service.storage.get_policy(active.id)
    replacement = service.storage.get_policy(review.replacement_policy_id or "")

    assert review.decision == PolicyReviewDecision.MODIFY
    assert old is not None and old.status == PolicyStatus.PAUSED
    assert replacement is not None
    assert replacement.status == PolicyStatus.DRAFT
    assert replacement.version == 2
    assert replacement.family_id == active.family_id
    assert replacement.supersedes_policy_id == active.id
    assert replacement.approved_at is None


def test_legacy_active_policy_gets_a_schedule_and_cannot_live_forever(
    tmp_path: Path,
) -> None:
    service = MemoryService(db_path=tmp_path / "memory.db")
    legacy_approval = datetime.now() - timedelta(days=60)
    legacy = Policy(
        brand_id="legacy-brand",
        target_agent=AgentType.SCHEDULER,
        version=1,
        status=PolicyStatus.ACTIVE,
        approved_by="legacy-reviewer",
        approved_at=legacy_approval,
        updated_at=legacy_approval,
        rules=[
            PolicyRule(
                description="Prefer an observed time bucket.",
                feature_name="time_bucket",
                feature_value="evening",
                source_insight_id="legacy-insight",
                confidence_0_1=0.70,
                priority=3,
            )
        ],
    )
    service.storage.save_policy(legacy)

    assert service.get_active_policies("legacy-brand") == []
    migrated = service.storage.get_policy(legacy.id)
    assert migrated is not None
    assert migrated.valid_from is not None
    assert migrated.next_review_at is not None
    assert migrated.status == PolicyStatus.EXPIRED
