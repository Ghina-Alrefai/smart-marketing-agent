from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from smart_social_contracts import AgentType

from adaptive_memory.adapters import adapt_brand_dna_payload
from adaptive_memory.engine import (
    ConsolidationConfig,
    InsightValidator,
    Learner,
    PolicyGenerator,
    PolicyReviewConfig,
    PolicyReviewer,
)
from adaptive_memory.models import (
    ConsolidationResult,
    IngestionResult,
    InsightStatus,
    Policy,
    PolicyReview,
    PolicyReviewBatchResult,
    PolicyReviewTrigger,
    PolicyStatus,
)
from adaptive_memory.storage import MemoryStorage, SQLiteStorage


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class MemoryService:
    """Single public facade between Brand-DNA/agents and Adaptive Memory internals.

    Ingestion, learning, policy drafting, and activation are deliberately separate
    operations. A payload can never activate a policy by itself.
    """

    def __init__(
        self,
        storage: MemoryStorage | None = None,
        *,
        db_path: str | Path = "adaptive_memory.db",
        consolidation_config: ConsolidationConfig | None = None,
        policy_review_config: PolicyReviewConfig | None = None,
    ):
        self.storage = storage or SQLiteStorage(db_path)
        self.consolidation_config = consolidation_config or ConsolidationConfig()
        self.learner = Learner(self.consolidation_config)
        self.validator = InsightValidator(
            consolidation_config=self.consolidation_config
        )
        self.policy_generator = PolicyGenerator()
        self.policy_review_config = policy_review_config or PolicyReviewConfig()
        self.policy_reviewer = PolicyReviewer(
            self.storage,
            config=self.policy_review_config,
            policy_generator=self.policy_generator,
        )

    def ingest_brand_dna_payload(
        self,
        payload: dict[str, Any],
        *,
        fallback_brand_id: str | None = None,
        fallback_page_id: str | None = None,
        success_only: bool = False,
    ) -> IngestionResult:
        envelope, events = adapt_brand_dna_payload(
            payload,
            fallback_brand_id=fallback_brand_id,
            fallback_page_id=fallback_page_id,
            success_only=success_only,
        )
        inserted, duplicate = self.storage.insert_evidence(events)
        parent_event_id = events[0].parent_event_id if events else (envelope.event_id or "skipped")
        return IngestionResult(
            parent_event_id=parent_event_id,
            extracted_count=len(envelope.feature_attributions),
            inserted_count=inserted,
            duplicate_count=duplicate,
            skipped_count=len(envelope.feature_attributions) - len(events),
        )

    def ingest_jsonl(
        self,
        path: str | Path,
        *,
        fallback_brand_id: str,
        fallback_page_id: str | None = None,
        success_only: bool = False,
    ) -> dict[str, Any]:
        input_path = Path(path)
        record_results: list[IngestionResult] = []
        with input_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    record_results.append(
                        self.ingest_brand_dna_payload(
                            payload,
                            fallback_brand_id=fallback_brand_id,
                            fallback_page_id=fallback_page_id,
                            success_only=success_only,
                        )
                    )
                except Exception as exc:
                    raise ValueError(
                        f"Failed to ingest JSONL record at line {line_number}: {exc}"
                    ) from exc
        return {
            "record_count": len(record_results),
            "extracted_count": sum(item.extracted_count for item in record_results),
            "inserted_count": sum(item.inserted_count for item in record_results),
            "duplicate_count": sum(item.duplicate_count for item in record_results),
            "skipped_count": sum(item.skipped_count for item in record_results),
        }

    def consolidate_insights(self, brand_id: str) -> ConsolidationResult:
        events = self.storage.list_evidence(brand_id=brand_id)
        candidates = self.learner.consolidate(events, brand_id)
        validated_count = 0
        rejected_count = 0
        for candidate in candidates:
            validated = self.validator.validate(candidate)
            self.storage.save_insight(validated)
            if validated.status == InsightStatus.VALIDATED:
                validated_count += 1
            else:
                rejected_count += 1
        return ConsolidationResult(
            brand_id=brand_id,
            evidence_count=len(events),
            candidate_insight_count=len(candidates),
            validated_insight_count=validated_count,
            rejected_insight_count=rejected_count,
        )

    def generate_draft_policies(self, brand_id: str) -> list[Policy]:
        insights = self.storage.list_insights(
            brand_id=brand_id, status=InsightStatus.VALIDATED
        )
        agents = sorted({item.target_agent for item in insights}, key=lambda item: item.value)
        versions = {
            agent: self.storage.next_policy_version(brand_id, agent) for agent in agents
        }
        generated = self.policy_generator.generate(
            insights,
            brand_id=brand_id,
            version_for_agent=versions,
        )

        saved: list[Policy] = []
        for policy in generated:
            source_set = set(policy.source_insight_ids)
            existing = self.storage.list_policies(
                brand_id=brand_id, target_agent=policy.target_agent
            )
            if any(set(item.source_insight_ids) == source_set for item in existing):
                continue
            self.storage.save_policy(policy)
            saved.append(policy)
        return saved

    def activate_policy(self, policy_id: str, approved_by: str) -> Policy:
        config = self.policy_review_config
        return self.storage.activate_policy(
            policy_id,
            approved_by,
            review_interval_days=config.review_interval_days,
            review_grace_days=config.review_grace_days,
            minimum_review_posts=config.minimum_evaluated_posts,
        )

    def review_policy(
        self,
        policy_id: str,
        *,
        reviewed_by: str,
        force: bool = False,
        now: datetime | None = None,
    ) -> PolicyReview:
        policy = self.storage.get_policy(policy_id)
        if policy is None:
            raise ValueError(f"Policy {policy_id!r} does not exist")
        # Refresh learned Insights first so a MODIFY decision can create a vNext
        # draft from the newest evidence instead of copying stale confidence.
        self.consolidate_insights(policy.brand_id)
        return self.policy_reviewer.review_policy(
            policy_id,
            reviewed_by=reviewed_by,
            trigger=PolicyReviewTrigger.MANUAL,
            force=force,
            now=now,
        )

    def review_due_policies(
        self,
        brand_id: str | None = None,
        *,
        reviewed_by: str = "policy-review-scheduler",
        now: datetime | None = None,
    ) -> PolicyReviewBatchResult:
        now = _as_utc(now or datetime.now(timezone.utc))
        self.policy_reviewer.backfill_active_schedules(brand_id=brand_id)
        active = self.storage.list_policies(
            brand_id=brand_id, status=PolicyStatus.ACTIVE
        )
        due_brands = {
            policy.brand_id
            for policy in active
            if policy.next_review_at is not None
            and _as_utc(policy.next_review_at) <= now
            and (policy.valid_until is None or now < _as_utc(policy.valid_until))
        }
        for due_brand in sorted(due_brands):
            self.consolidate_insights(due_brand)
        return self.policy_reviewer.review_due_policies(
            brand_id=brand_id,
            reviewed_by=reviewed_by,
            now=now,
        )

    def list_policy_reviews(
        self,
        *,
        brand_id: str | None = None,
        policy_id: str | None = None,
        limit: int | None = None,
    ) -> list[PolicyReview]:
        return self.storage.list_policy_reviews(
            brand_id=brand_id,
            policy_id=policy_id,
            limit=limit,
        )

    def get_policy_health(
        self,
        brand_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = _as_utc(now or datetime.now(timezone.utc))
        migrated = self.policy_reviewer.backfill_active_schedules(brand_id=brand_id)
        expired_now = self.policy_reviewer.expire_past_validity(
            brand_id=brand_id, now=now
        )
        active = self.storage.list_policies(
            brand_id=brand_id, status=PolicyStatus.ACTIVE
        )
        due = [
            policy
            for policy in active
            if policy.next_review_at is not None
            and _as_utc(policy.next_review_at) <= now
        ]
        deferred = [
            policy for policy in active if policy.insufficient_review_count > 0
        ]
        return {
            "active_policy_count": len(active),
            "due_policy_count": len(due),
            "deferred_policy_count": len(deferred),
            "expired_policy_count": len(
                self.storage.list_policies(
                    brand_id=brand_id, status=PolicyStatus.EXPIRED
                )
            ),
            "migrated_schedule_count": len(migrated),
            "expired_now_count": len(expired_now),
            "review_interval_days": self.policy_review_config.review_interval_days,
            "minimum_evaluated_posts": self.policy_review_config.minimum_evaluated_posts,
        }

    def get_active_policies(
        self,
        brand_id: str,
        target_agent: AgentType | None = None,
    ) -> list[Policy]:
        now = datetime.now(timezone.utc)
        self.policy_reviewer.expire_past_validity(brand_id=brand_id, now=now)
        policies = self.storage.list_policies(
            brand_id=brand_id,
            target_agent=target_agent,
            status=PolicyStatus.ACTIVE,
        )
        return [policy for policy in policies if policy.is_effective(now)]

    def get_agent_policy_context(
        self,
        brand_id: str,
        target_agent: AgentType,
        runtime_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_context = runtime_context or {}
        applicable_rules = []
        for policy in self.get_active_policies(brand_id, target_agent):
            for rule in policy.rules:
                if all(runtime_context.get(key) == value for key, value in rule.conditions.items()):
                    applicable_rules.append(
                        {
                            "policy_id": policy.id,
                            "policy_version": policy.version,
                            "description": rule.description,
                            "feature_name": rule.feature_name,
                            "feature_value": rule.feature_value,
                            "conditions": rule.conditions,
                            "priority": rule.priority,
                            "confidence_0_1": rule.confidence_0_1,
                            "source_insight_id": rule.source_insight_id,
                            "is_hard_constraint": rule.is_hard_constraint,
                        }
                    )
        applicable_rules.sort(key=lambda item: (item["priority"], -item["confidence_0_1"]))
        return {
            "brand_id": brand_id,
            "target_agent": target_agent.value,
            "runtime_context": runtime_context,
            "rules": applicable_rules,
        }

    def stats(self) -> dict[str, int]:
        return self.storage.stats()

    def close(self) -> None:
        self.storage.close()
