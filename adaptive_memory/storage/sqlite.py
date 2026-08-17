from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from smart_social_contracts import AgentType

from adaptive_memory.models import (
    EvidenceEvent,
    Insight,
    InsightStatus,
    Policy,
    PolicyStatus,
)

from .base import MemoryStorage


class SQLiteStorage(MemoryStorage):
    """Fully tested local storage used as the MVP source of truth."""

    def __init__(self, db_path: str | Path = "adaptive_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_events (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    parent_event_id TEXT NOT NULL,
                    brand_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    feature_name TEXT NOT NULL,
                    owner_agent TEXT NOT NULL,
                    feature_role TEXT NOT NULL,
                    actual_success INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    data TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_brand
                    ON evidence_events (brand_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_feature
                    ON evidence_events (brand_id, feature_name);
                CREATE INDEX IF NOT EXISTS idx_evidence_agent
                    ON evidence_events (brand_id, owner_agent);
                CREATE INDEX IF NOT EXISTS idx_evidence_outcome
                    ON evidence_events (brand_id, actual_success);

                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    group_key TEXT NOT NULL UNIQUE,
                    brand_id TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    feature_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_insights_brand_agent
                    ON insights (brand_id, target_agent, status);

                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY,
                    brand_id TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL,
                    UNIQUE (brand_id, target_agent, version)
                );

                CREATE INDEX IF NOT EXISTS idx_policies_brand_agent
                    ON policies (brand_id, target_agent, status);
                """
            )

    def insert_evidence(self, events: Iterable[EvidenceEvent]) -> tuple[int, int]:
        inserted = 0
        duplicate = 0
        with self._connect() as conn:
            for event in events:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO evidence_events (
                        id, idempotency_key, parent_event_id, brand_id, post_id,
                        feature_name, owner_agent, feature_role, actual_success,
                        observed_at, data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.idempotency_key,
                        event.parent_event_id,
                        event.brand_id,
                        event.post_id,
                        event.feature_name,
                        event.owner_agent.value,
                        event.feature_role.value,
                        1 if event.actual_success else 0,
                        event.observed_at.isoformat(),
                        event.model_dump_json(),
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    duplicate += 1
        return inserted, duplicate

    def list_evidence(
        self,
        *,
        brand_id: str | None = None,
        feature_name: str | None = None,
        owner_agent: AgentType | None = None,
        actual_success: bool | None = None,
    ) -> list[EvidenceEvent]:
        query = "SELECT data FROM evidence_events"
        conditions: list[str] = []
        params: list[object] = []
        if brand_id is not None:
            conditions.append("brand_id = ?")
            params.append(brand_id)
        if feature_name is not None:
            conditions.append("feature_name = ?")
            params.append(feature_name)
        if owner_agent is not None:
            conditions.append("owner_agent = ?")
            params.append(owner_agent.value)
        if actual_success is not None:
            conditions.append("actual_success = ?")
            params.append(1 if actual_success else 0)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY observed_at, id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [EvidenceEvent.model_validate_json(row["data"]) for row in rows]

    def save_insight(self, insight: Insight) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO insights (
                    id, group_key, brand_id, target_agent, feature_name,
                    status, confidence, updated_at, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_key) DO UPDATE SET
                    id=excluded.id,
                    brand_id=excluded.brand_id,
                    target_agent=excluded.target_agent,
                    feature_name=excluded.feature_name,
                    status=excluded.status,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at,
                    data=excluded.data
                """,
                (
                    insight.id,
                    insight.group_key,
                    insight.brand_id,
                    insight.target_agent.value,
                    insight.feature_name,
                    insight.status.value,
                    insight.confidence_0_1,
                    insight.updated_at.isoformat(),
                    insight.model_dump_json(),
                ),
            )
        return insight.id

    def get_insight(self, insight_id: str) -> Insight | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM insights WHERE id = ?", (insight_id,)
            ).fetchone()
        return Insight.model_validate_json(row["data"]) if row else None

    def list_insights(
        self,
        *,
        brand_id: str | None = None,
        target_agent: AgentType | None = None,
        status: InsightStatus | None = None,
    ) -> list[Insight]:
        query = "SELECT data FROM insights"
        conditions: list[str] = []
        params: list[object] = []
        if brand_id is not None:
            conditions.append("brand_id = ?")
            params.append(brand_id)
        if target_agent is not None:
            conditions.append("target_agent = ?")
            params.append(target_agent.value)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY confidence DESC, updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Insight.model_validate_json(row["data"]) for row in rows]

    def save_policy(self, policy: Policy) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO policies (
                    id, brand_id, target_agent, version, status, updated_at, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    brand_id=excluded.brand_id,
                    target_agent=excluded.target_agent,
                    version=excluded.version,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    data=excluded.data
                """,
                (
                    policy.id,
                    policy.brand_id,
                    policy.target_agent.value,
                    policy.version,
                    policy.status.value,
                    policy.updated_at.isoformat(),
                    policy.model_dump_json(),
                ),
            )
        return policy.id

    def update_policy(self, policy: Policy) -> bool:
        if self.get_policy(policy.id) is None:
            return False
        self.save_policy(policy)
        return True

    def get_policy(self, policy_id: str) -> Policy | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM policies WHERE id = ?", (policy_id,)
            ).fetchone()
        return Policy.model_validate_json(row["data"]) if row else None

    def list_policies(
        self,
        *,
        brand_id: str | None = None,
        target_agent: AgentType | None = None,
        status: PolicyStatus | None = None,
    ) -> list[Policy]:
        query = "SELECT data FROM policies"
        conditions: list[str] = []
        params: list[object] = []
        if brand_id is not None:
            conditions.append("brand_id = ?")
            params.append(brand_id)
        if target_agent is not None:
            conditions.append("target_agent = ?")
            params.append(target_agent.value)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY target_agent, version DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Policy.model_validate_json(row["data"]) for row in rows]

    def next_policy_version(self, brand_id: str, target_agent: AgentType) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS max_version
                FROM policies WHERE brand_id = ? AND target_agent = ?
                """,
                (brand_id, target_agent.value),
            ).fetchone()
        return int(row["max_version"]) + 1

    def activate_policy(self, policy_id: str, approved_by: str) -> Policy:
        if not approved_by.strip():
            raise ValueError("approved_by must be a non-empty human/system identifier")
        target = self.get_policy(policy_id)
        if target is None:
            raise ValueError(f"Policy {policy_id!r} does not exist")
        if target.status not in {PolicyStatus.DRAFT, PolicyStatus.PAUSED}:
            raise ValueError(
                f"Only draft or paused policies can be activated; got {target.status.value}"
            )

        now = datetime.now(timezone.utc)
        active = target.model_copy(
            update={
                "status": PolicyStatus.ACTIVE,
                "approved_by": approved_by.strip(),
                "approved_at": now,
                "updated_at": now,
            }
        )
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT data FROM policies
                WHERE brand_id = ? AND target_agent = ? AND status = ?
                """,
                (
                    target.brand_id,
                    target.target_agent.value,
                    PolicyStatus.ACTIVE.value,
                ),
            ).fetchall()
            for row in rows:
                old = Policy.model_validate_json(row["data"])
                deprecated = old.model_copy(
                    update={
                        "status": PolicyStatus.DEPRECATED,
                        "updated_at": now,
                    }
                )
                conn.execute(
                    """
                    UPDATE policies SET status = ?, updated_at = ?, data = ?
                    WHERE id = ?
                    """,
                    (
                        deprecated.status.value,
                        deprecated.updated_at.isoformat(),
                        deprecated.model_dump_json(),
                        deprecated.id,
                    ),
                )
            conn.execute(
                """
                UPDATE policies SET status = ?, updated_at = ?, data = ?
                WHERE id = ?
                """,
                (
                    active.status.value,
                    active.updated_at.isoformat(),
                    active.model_dump_json(),
                    active.id,
                ),
            )
        return active

    def stats(self) -> dict[str, int]:
        tables = ["evidence_events", "insights", "policies"]
        output: dict[str, int] = {}
        with self._connect() as conn:
            for table in tables:
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                output[table] = int(row["count"])
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM policies WHERE status = ?",
                (PolicyStatus.ACTIVE.value,),
            ).fetchone()
            output["active_policies"] = int(row["count"])
        return output

    def close(self) -> None:
        # Connections are short-lived context managers, so there is nothing to close.
        return None
