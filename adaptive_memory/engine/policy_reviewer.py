from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Iterable

from adaptive_memory.models import (
    EvidenceEvent,
    InsightStatus,
    Policy,
    PolicyReview,
    PolicyReviewBatchResult,
    PolicyReviewDecision,
    PolicyReviewTrigger,
    PolicyRule,
    PolicyRuleReviewMetric,
    PolicyStatus,
)
from adaptive_memory.storage import MemoryStorage

from .policy_generator import PolicyGenerator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


@dataclass(frozen=True, slots=True)
class PolicyReviewConfig:
    """Configurable MVP thresholds; none of these values is a scientific claim."""

    review_interval_days: int = 30
    review_grace_days: int = 15
    minimum_evaluated_posts: int = 8
    insufficient_evidence_deferral_days: int = 14
    max_insufficient_reviews: int = 2
    baseline_lookback_days: int = 30
    renew_min_success_rate_0_1: float = 0.60
    modify_min_success_rate_0_1: float = 0.50
    expire_below_success_rate_0_1: float = 0.35
    renew_min_delta: float = -0.05
    modify_min_delta: float = -0.15
    expire_max_delta: float = -0.25

    def __post_init__(self) -> None:
        if self.review_interval_days < 1:
            raise ValueError("review_interval_days must be at least 1")
        if self.review_grace_days < 0:
            raise ValueError("review_grace_days cannot be negative")
        if self.minimum_evaluated_posts < 1:
            raise ValueError("minimum_evaluated_posts must be at least 1")
        if self.insufficient_evidence_deferral_days < 1:
            raise ValueError("insufficient_evidence_deferral_days must be at least 1")
        if self.max_insufficient_reviews < 0:
            raise ValueError("max_insufficient_reviews cannot be negative")
        if self.baseline_lookback_days < 1:
            raise ValueError("baseline_lookback_days must be at least 1")
        if not (
            0.0
            <= self.expire_below_success_rate_0_1
            < self.modify_min_success_rate_0_1
            <= self.renew_min_success_rate_0_1
            <= 1.0
        ):
            raise ValueError(
                "success-rate thresholds must satisfy 0 <= expire < modify <= renew <= 1"
            )


class PolicyReviewer:
    """Reviews time-bounded performance policies using explicitly linked posts.

    A post counts only when its Evidence context contains the policy ID that was
    injected during generation. This avoids falsely treating every later post as
    proof that the policy caused its outcome.
    """

    def __init__(
        self,
        storage: MemoryStorage,
        *,
        config: PolicyReviewConfig | None = None,
        policy_generator: PolicyGenerator | None = None,
    ):
        self.storage = storage
        self.config = config or PolicyReviewConfig()
        self.policy_generator = policy_generator or PolicyGenerator()

    def expire_past_validity(
        self,
        *,
        brand_id: str | None = None,
        now: datetime | None = None,
    ) -> list[Policy]:
        now = as_utc(now or utc_now())
        self.backfill_active_schedules(brand_id=brand_id)
        expired: list[Policy] = []
        for policy in self.storage.list_policies(
            brand_id=brand_id, status=PolicyStatus.ACTIVE
        ):
            if policy.valid_until is None or now < as_utc(policy.valid_until):
                continue
            updated = policy.model_copy(
                update={
                    "status": PolicyStatus.EXPIRED,
                    "valid_until": now,
                    "expiration_reason": "review_grace_period_elapsed",
                    "last_review_reason": (
                        "تجاوزت السياسة آخر حد للصلاحية من دون تجديد مكتمل."
                    ),
                    "updated_at": now,
                }
            )
            self.storage.update_policy(updated)
            expired.append(updated)
        return expired

    def backfill_active_schedules(
        self, *, brand_id: str | None = None
    ) -> list[Policy]:
        """Safely migrate active policies written by releases before v1.3.0."""

        migrated: list[Policy] = []
        for policy in self.storage.list_policies(
            brand_id=brand_id, status=PolicyStatus.ACTIVE
        ):
            if policy.next_review_at is not None and policy.valid_until is not None:
                continue
            base = as_utc(
                policy.valid_from or policy.approved_at or policy.updated_at
            )
            interval = policy.review_interval_days or self.config.review_interval_days
            grace = policy.review_grace_days
            next_review = base + timedelta(days=interval)
            updated = policy.model_copy(
                update={
                    "valid_from": policy.valid_from or base,
                    "next_review_at": next_review,
                    "valid_until": next_review + timedelta(days=grace),
                    "minimum_review_posts": max(
                        policy.minimum_review_posts,
                        self.config.minimum_evaluated_posts,
                    ),
                    "updated_at": utc_now(),
                }
            )
            self.storage.update_policy(updated)
            migrated.append(updated)
        return migrated

    def review_due_policies(
        self,
        *,
        brand_id: str | None = None,
        reviewed_by: str = "policy-review-scheduler",
        now: datetime | None = None,
    ) -> PolicyReviewBatchResult:
        now = as_utc(now or utc_now())
        expired = self.expire_past_validity(brand_id=brand_id, now=now)
        active = self.storage.list_policies(
            brand_id=brand_id, status=PolicyStatus.ACTIVE
        )
        due = [
            policy
            for policy in active
            if policy.next_review_at is not None
            and as_utc(policy.next_review_at) <= now
        ]
        reviews = [
            self.review_policy(
                policy.id,
                reviewed_by=reviewed_by,
                trigger=PolicyReviewTrigger.SCHEDULED,
                force=True,
                now=now,
            )
            for policy in due
        ]
        counts = Counter(item.decision.value for item in reviews)
        return PolicyReviewBatchResult(
            brand_id=brand_id,
            checked_policy_count=len(active) + len(expired),
            reviewed_policy_count=len(reviews),
            expired_without_review_count=len(expired),
            decision_counts=dict(counts),
            reviews=reviews,
        )

    def review_policy(
        self,
        policy_id: str,
        *,
        reviewed_by: str,
        trigger: PolicyReviewTrigger = PolicyReviewTrigger.MANUAL,
        force: bool = False,
        now: datetime | None = None,
    ) -> PolicyReview:
        now = as_utc(now or utc_now())
        actor = reviewed_by.strip()
        if not actor:
            raise ValueError("reviewed_by must be a non-empty identifier")
        policy = self.storage.get_policy(policy_id)
        if policy is None:
            raise ValueError(f"Policy {policy_id!r} does not exist")
        if policy.status != PolicyStatus.ACTIVE:
            raise ValueError(
                f"Only active policies can be reviewed; got {policy.status.value}"
            )
        if policy.valid_until is not None and now >= as_utc(policy.valid_until):
            self.expire_past_validity(brand_id=policy.brand_id, now=now)
            raise ValueError("Policy expired because its review grace period elapsed")
        if not force and (
            policy.next_review_at is None or as_utc(policy.next_review_at) > now
        ):
            raise ValueError(
                "Policy is not due for review yet; use force for a manual review"
            )

        window_start = as_utc(
            policy.last_review_at
            or policy.valid_from
            or policy.approved_at
            or policy.created_at
        )
        all_events = self.storage.list_evidence(brand_id=policy.brand_id)
        linked = [
            event
            for event in all_events
            if window_start <= as_utc(event.observed_at) <= now
            and self._event_applied_policy(event, policy.id)
        ]
        linked_posts = self._unique_posts(linked)
        success_count = sum(1 for event in linked_posts if event.actual_success)
        failure_count = len(linked_posts) - success_count
        success_rate = (
            success_count / len(linked_posts) if linked_posts else None
        )

        baseline_start = window_start - timedelta(
            days=self.config.baseline_lookback_days
        )
        baseline_events = [
            event
            for event in all_events
            if baseline_start <= as_utc(event.observed_at) < window_start
        ]
        baseline_posts = self._unique_posts(baseline_events)
        baseline_rate = (
            sum(1 for event in baseline_posts if event.actual_success)
            / len(baseline_posts)
            if baseline_posts
            else None
        )
        delta = (
            success_rate - baseline_rate
            if success_rate is not None and baseline_rate is not None
            else None
        )
        mean_rpi = self._mean_metric(
            linked_posts, "relative_performance_index"
        )
        rule_metrics = [self._rule_metric(rule, linked) for rule in policy.rules]
        mean_confidence = (
            mean(rule.confidence_0_1 for rule in policy.rules)
            if policy.rules
            else 0.0
        )

        minimum_posts = max(
            policy.minimum_review_posts, self.config.minimum_evaluated_posts
        )
        decision, reasons = self._decide(
            evaluated_post_count=len(linked_posts),
            minimum_posts=minimum_posts,
            success_rate=success_rate,
            baseline_rate=baseline_rate,
            delta=delta,
        )
        replacement_policy_id: str | None = None

        if decision == PolicyReviewDecision.INSUFFICIENT_EVIDENCE:
            decision, reasons = self._handle_insufficient_evidence(
                policy, now=now, reasons=reasons
            )
        elif decision == PolicyReviewDecision.RENEW:
            self._renew(policy, now=now, reasons=reasons)
        elif decision == PolicyReviewDecision.MODIFY:
            replacement = self._create_replacement_draft(policy, now=now)
            if replacement is None:
                decision = PolicyReviewDecision.SUSPEND
                reasons.append(
                    "لا توجد حالياً قواعد بديلة محققة يمكن وضعها في إصدار جديد."
                )
                self._suspend(policy, decision=decision, now=now, reasons=reasons)
            else:
                replacement_policy_id = replacement.id
                self._suspend(
                    policy,
                    decision=decision,
                    now=now,
                    reasons=reasons,
                    replacement_policy_id=replacement.id,
                )
        elif decision == PolicyReviewDecision.SUSPEND:
            self._suspend(policy, decision=decision, now=now, reasons=reasons)
        else:
            self._expire(policy, now=now, reasons=reasons)

        review = PolicyReview(
            policy_id=policy.id,
            family_id=policy.family_id or policy.id,
            policy_version=policy.version,
            brand_id=policy.brand_id,
            target_agent=policy.target_agent,
            trigger=trigger,
            decision=decision,
            reviewed_by=actor,
            reviewed_at=now,
            evidence_window_start=window_start,
            evidence_window_end=now,
            minimum_required_posts=minimum_posts,
            linked_evidence_count=len(linked),
            evaluated_post_count=len(linked_posts),
            success_count=success_count,
            failure_count=failure_count,
            success_rate_0_1=success_rate,
            baseline_success_rate_0_1=baseline_rate,
            success_rate_delta=delta,
            mean_relative_performance_index=mean_rpi,
            previous_mean_rule_confidence_0_1=mean_confidence,
            rule_metrics=rule_metrics,
            reasons=reasons,
            replacement_policy_id=replacement_policy_id,
        )
        self.storage.save_policy_review(review)
        return review

    def _decide(
        self,
        *,
        evaluated_post_count: int,
        minimum_posts: int,
        success_rate: float | None,
        baseline_rate: float | None,
        delta: float | None,
    ) -> tuple[PolicyReviewDecision, list[str]]:
        if evaluated_post_count < minimum_posts or success_rate is None:
            return PolicyReviewDecision.INSUFFICIENT_EVIDENCE, [
                f"يتوفر {evaluated_post_count} منشورات مقيمة ومرتبطة بالسياسة صراحةً؛ "
                f"بينما يلزم {minimum_posts}."
            ]

        reasons = [f"معدل نجاح المنشورات المرتبطة هو {success_rate:.3f}."]
        if baseline_rate is not None and delta is not None:
            reasons.append(
                f"معدل خط الأساس {baseline_rate:.3f}، والفرق {delta:+.3f}."
            )

        baseline_allows_renew = delta is None or delta >= self.config.renew_min_delta
        if (
            success_rate >= self.config.renew_min_success_rate_0_1
            and baseline_allows_renew
        ):
            return PolicyReviewDecision.RENEW, reasons

        baseline_requires_expiry = (
            delta is not None and delta <= self.config.expire_max_delta
        )
        if (
            success_rate < self.config.expire_below_success_rate_0_1
            or baseline_requires_expiry
        ):
            return PolicyReviewDecision.EXPIRE, reasons

        baseline_allows_modify = (
            delta is None or delta >= self.config.modify_min_delta
        )
        if (
            success_rate >= self.config.modify_min_success_rate_0_1
            and baseline_allows_modify
        ):
            reasons.append("يلزم إصدار مسودة معدلة قبل أن تستمر هذه السياسة.")
            return PolicyReviewDecision.MODIFY, reasons

        reasons.append("الأداء غير حاسم أو أضعف مادياً من المستوى المتوقع.")
        return PolicyReviewDecision.SUSPEND, reasons

    def _handle_insufficient_evidence(
        self,
        policy: Policy,
        *,
        now: datetime,
        reasons: list[str],
    ) -> tuple[PolicyReviewDecision, list[str]]:
        count = policy.insufficient_review_count + 1
        if count > self.config.max_insufficient_reviews:
            reasons.append(
                "تم تجاوز الحد الأعلى لتأجيلات نقص الدليل؛ لذلك أوقفت السياسة مؤقتاً."
            )
            self._suspend(
                policy,
                decision=PolicyReviewDecision.SUSPEND,
                now=now,
                reasons=reasons,
                insufficient_review_count=count,
            )
            return PolicyReviewDecision.SUSPEND, reasons

        next_review = now + timedelta(
            days=self.config.insufficient_evidence_deferral_days
        )
        updated = policy.model_copy(
            update={
                "last_review_at": now,
                "next_review_at": next_review,
                "valid_until": next_review
                + timedelta(days=policy.review_grace_days),
                "insufficient_review_count": count,
                "last_review_decision": PolicyReviewDecision.INSUFFICIENT_EVIDENCE,
                "last_review_reason": " ".join(reasons),
                "updated_at": now,
            }
        )
        self.storage.update_policy(updated)
        return PolicyReviewDecision.INSUFFICIENT_EVIDENCE, reasons

    def _renew(self, policy: Policy, *, now: datetime, reasons: list[str]) -> None:
        next_review = now + timedelta(days=policy.review_interval_days)
        updated = policy.model_copy(
            update={
                "status": PolicyStatus.ACTIVE,
                "last_review_at": now,
                "next_review_at": next_review,
                "valid_until": next_review + timedelta(days=policy.review_grace_days),
                "insufficient_review_count": 0,
                "last_review_decision": PolicyReviewDecision.RENEW,
                "last_review_reason": " ".join(reasons),
                "expiration_reason": None,
                "updated_at": now,
            }
        )
        self.storage.update_policy(updated)

    def _suspend(
        self,
        policy: Policy,
        *,
        decision: PolicyReviewDecision,
        now: datetime,
        reasons: list[str],
        replacement_policy_id: str | None = None,
        insufficient_review_count: int | None = None,
    ) -> None:
        updates = {
            "status": PolicyStatus.PAUSED,
            "last_review_at": now,
            "next_review_at": None,
            "valid_until": now,
            "last_review_decision": decision,
            "last_review_reason": " ".join(reasons),
            "replacement_policy_id": replacement_policy_id,
            "updated_at": now,
        }
        if insufficient_review_count is not None:
            updates["insufficient_review_count"] = insufficient_review_count
        self.storage.update_policy(policy.model_copy(update=updates))

    def _expire(self, policy: Policy, *, now: datetime, reasons: list[str]) -> None:
        self.storage.update_policy(
            policy.model_copy(
                update={
                    "status": PolicyStatus.EXPIRED,
                    "last_review_at": now,
                    "next_review_at": None,
                    "valid_until": now,
                    "last_review_decision": PolicyReviewDecision.EXPIRE,
                    "last_review_reason": " ".join(reasons),
                    "expiration_reason": "review_found_policy_ineffective",
                    "updated_at": now,
                }
            )
        )

    def _create_replacement_draft(
        self, policy: Policy, *, now: datetime
    ) -> Policy | None:
        insights = self.storage.list_insights(
            brand_id=policy.brand_id,
            target_agent=policy.target_agent,
            status=InsightStatus.VALIDATED,
        )
        generated = self.policy_generator.generate(
            insights,
            brand_id=policy.brand_id,
            version_for_agent={
                policy.target_agent: self.storage.next_policy_version(
                    policy.brand_id, policy.target_agent
                )
            },
        )
        if not generated:
            return None
        replacement = generated[0].model_copy(
            update={
                "family_id": policy.family_id or policy.id,
                "supersedes_policy_id": policy.id,
                "review_interval_days": policy.review_interval_days,
                "review_grace_days": policy.review_grace_days,
                "minimum_review_posts": policy.minimum_review_posts,
                "created_at": now,
                "updated_at": now,
            }
        )
        self.storage.save_policy(replacement)
        return replacement

    @staticmethod
    def _event_applied_policy(event: EvidenceEvent, policy_id: str) -> bool:
        ids = event.context.get("applied_policy_ids")
        if ids is None:
            ids = event.context.get("memory_policy_ids")
        if not isinstance(ids, list):
            return False
        return policy_id in {str(item) for item in ids}

    @staticmethod
    def _unique_posts(events: Iterable[EvidenceEvent]) -> list[EvidenceEvent]:
        by_post: dict[str, EvidenceEvent] = {}
        for event in sorted(events, key=lambda item: (item.observed_at, item.id)):
            by_post.setdefault(event.post_id, event)
        return list(by_post.values())

    def _rule_metric(
        self, rule: PolicyRule, linked_events: list[EvidenceEvent]
    ) -> PolicyRuleReviewMetric:
        relevant = [
            event
            for event in linked_events
            if event.feature_name == rule.feature_name
        ]
        posts = self._unique_posts(relevant)
        success_count = sum(1 for event in posts if event.actual_success)
        return PolicyRuleReviewMetric(
            rule_id=rule.id,
            feature_name=rule.feature_name,
            linked_evidence_count=len(relevant),
            evaluated_post_count=len(posts),
            success_count=success_count,
            failure_count=len(posts) - success_count,
            success_rate_0_1=(success_count / len(posts) if posts else None),
            mean_relative_performance_index=self._mean_metric(
                posts, "relative_performance_index"
            ),
        )

    @staticmethod
    def _mean_metric(events: Iterable[EvidenceEvent], key: str) -> float | None:
        values = [
            float(event.actual_performance[key])
            for event in events
            if event.actual_performance.get(key) is not None
        ]
        return mean(values) if values else None
