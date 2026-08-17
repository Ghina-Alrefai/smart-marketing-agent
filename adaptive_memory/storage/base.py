from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from smart_social_contracts import AgentType

from adaptive_memory.models import EvidenceEvent, Insight, InsightStatus, Policy, PolicyStatus


class MemoryStorage(ABC):
    """Stable persistence contract used by the service and engines."""

    @abstractmethod
    def insert_evidence(self, events: Iterable[EvidenceEvent]) -> tuple[int, int]:
        """Return (inserted_count, duplicate_count)."""

    @abstractmethod
    def list_evidence(
        self,
        *,
        brand_id: str | None = None,
        feature_name: str | None = None,
        owner_agent: AgentType | None = None,
        actual_success: bool | None = None,
    ) -> list[EvidenceEvent]:
        pass

    @abstractmethod
    def save_insight(self, insight: Insight) -> str:
        pass

    @abstractmethod
    def get_insight(self, insight_id: str) -> Insight | None:
        pass

    @abstractmethod
    def list_insights(
        self,
        *,
        brand_id: str | None = None,
        target_agent: AgentType | None = None,
        status: InsightStatus | None = None,
    ) -> list[Insight]:
        pass

    @abstractmethod
    def save_policy(self, policy: Policy) -> str:
        pass

    @abstractmethod
    def update_policy(self, policy: Policy) -> bool:
        pass

    @abstractmethod
    def get_policy(self, policy_id: str) -> Policy | None:
        pass

    @abstractmethod
    def list_policies(
        self,
        *,
        brand_id: str | None = None,
        target_agent: AgentType | None = None,
        status: PolicyStatus | None = None,
    ) -> list[Policy]:
        pass

    @abstractmethod
    def next_policy_version(self, brand_id: str, target_agent: AgentType) -> int:
        pass

    @abstractmethod
    def activate_policy(self, policy_id: str, approved_by: str) -> Policy:
        pass

    @abstractmethod
    def stats(self) -> dict[str, int]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
