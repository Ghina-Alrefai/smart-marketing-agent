"""Persistent, user-facing progress state for campaign generation.

The campaign runs in a background task, so in-memory callbacks alone are not
enough for the frontend.  This tracker stores a small JSON snapshot on the
``ContentPlan`` after every meaningful hand-off between agents.  The snapshot
is intentionally presentation-friendly while remaining independent from the
React component that renders it.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tools.db_tools import update_plan_generation_state


PIPELINE_VERSION = "campaign-pipeline-progress-v2"

# Scheduler is visible so the user understands what happens after generation,
# but it is not part of the generation percentage because it waits for a human
# approval decision by design.
PIPELINE_NODES: tuple[dict[str, Any], ...] = (
    {"key": "orchestrator", "phase": "planning", "weight": 4},
    {"key": "brand", "phase": "planning", "weight": 10},
    {"key": "strategy", "phase": "planning", "weight": 11},
    {"key": "products", "phase": "planning", "weight": 7},
    {"key": "ideas", "phase": "planning", "weight": 10},
    {"key": "copywriter", "phase": "production", "weight": 18},
    {"key": "evaluator", "phase": "production", "weight": 12},
    {"key": "designer", "phase": "production", "weight": 18},
    {"key": "quality", "phase": "production", "weight": 7},
    {"key": "assembler", "phase": "delivery", "weight": 3},
    {"key": "scheduler", "phase": "delivery", "weight": 0},
)

PRODUCTION_NODE_KEYS = {"copywriter", "evaluator", "designer", "quality"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def new_pipeline_state(
    *,
    status: str = "queued",
    execution_mode: str = "live",
) -> dict[str, Any]:
    """Return a fresh serialisable state for a new generation attempt."""
    created_at = _iso()
    is_demo = execution_mode == "offline_demo"
    return {
        "version": PIPELINE_VERSION,
        "run_id": f"run_{uuid4().hex[:16]}",
        "execution_mode": execution_mode,
        "is_demo": is_demo,
        "disclosure": (
            "وضع العرض دون اتصال — تسلسل توضيحي ونتائج محضّرة مسبقاً؛ "
            "لا تُجرى استدعاءات لنماذج الذكاء الاصطناعي."
            if is_demo
            else None
        ),
        "external_ai_calls": 0 if is_demo else None,
        "status": status,
        "active_node": None,
        "overall_progress": 0,
        "total_posts": 0,
        "posts_generated": 0,
        "failed_posts": 0,
        "current_post": None,
        "started_at": created_at if status == "running" else None,
        "updated_at": created_at,
        "completed_at": None,
        "event_count": 0,
        "nodes": [
            {
                **definition,
                "status": "pending",
                "activity": "في الانتظار",
                "output_summary": None,
                "started_at": None,
                "completed_at": None,
                "completed_items": 0,
                "failed_items": 0,
                "total_items": 0,
            }
            for definition in PIPELINE_NODES
        ],
        "events": [],
        "error": None,
    }


class CampaignPipelineProgress:
    """Own and persist one campaign attempt's observable progress."""

    def __init__(self, plan_id: int, *, execution_mode: str = "live") -> None:
        self.plan_id = plan_id
        self.state = new_pipeline_state(
            status="running",
            execution_mode=execution_mode,
        )
        self._item_started_at: dict[tuple[str, int], datetime] = {}
        self._append_event(
            "orchestrator",
            "queued",
            (
                "تم استلام طلب العرض وتجهيز التسلسل التوضيحي دون اتصال."
                if execution_mode == "offline_demo"
                else "تم استلام طلب الحملة وتجهيز خط التنفيذ."
            ),
        )
        self._persist(clear_error=True)

    @property
    def active_node(self) -> str | None:
        value = self.state.get("active_node")
        return str(value) if value else None

    def _node(self, key: str) -> dict[str, Any]:
        for node in self.state["nodes"]:
            if node["key"] == key:
                return node
        raise KeyError(f"Unknown campaign pipeline node: {key}")

    def _append_event(
        self,
        node_key: str,
        event_status: str,
        message: str,
        *,
        detail: str | None = None,
        post_index: int | None = None,
        total_posts: int | None = None,
        metadata: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        self.state["event_count"] = int(self.state.get("event_count") or 0) + 1
        event = {
            "sequence": self.state["event_count"],
            "node_key": node_key,
            "status": event_status,
            "message": message,
            "detail": detail,
            "at": _iso(),
            "post_index": post_index,
            "total_posts": total_posts,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }
        events = list(self.state.get("events") or [])
        events.append(event)
        # A bounded history keeps polling payloads small even for 30-post runs.
        self.state["events"] = events[-80:]

    def _recalculate_progress(self) -> None:
        earned = 0.0
        total_weight = sum(float(node["weight"]) for node in self.state["nodes"])
        for node in self.state["nodes"]:
            weight = float(node["weight"])
            if weight <= 0:
                continue
            if node["status"] == "completed":
                fraction = 1.0
            elif node["key"] in PRODUCTION_NODE_KEYS and node["total_items"]:
                fraction = min(
                    1.0,
                    (node["completed_items"] + (0.18 if node["status"] == "active" else 0))
                    / node["total_items"],
                )
            elif node["status"] == "active":
                fraction = 0.18
            else:
                fraction = 0.0
            earned += weight * fraction
        self.state["overall_progress"] = min(
            99,
            max(0, round((earned / total_weight) * 100)) if total_weight else 0,
        )

    def _persist(
        self,
        *,
        current_stage: str | None = None,
        status: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> None:
        self.state["updated_at"] = _iso()
        self._recalculate_progress()
        update_plan_generation_state(
            self.plan_id,
            status=status,
            current_stage=current_stage,
            error_message=error_message,
            clear_error=clear_error,
            pipeline_state=deepcopy(self.state),
        )

    def set_total_posts(self, total_posts: int) -> None:
        total = max(0, int(total_posts))
        self.state["total_posts"] = total
        for key in PRODUCTION_NODE_KEYS:
            self._node(key)["total_items"] = total
        self._persist()

    def activate(
        self,
        node_key: str,
        activity: str,
        *,
        detail: str | None = None,
        current_stage: str | None = None,
        post_index: int | None = None,
        total_posts: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        previous_key = self.active_node
        if previous_key and previous_key != node_key:
            previous = self._node(previous_key)
            if previous["status"] == "active":
                previous["status"] = (
                    "waiting" if previous_key in PRODUCTION_NODE_KEYS else "pending"
                )

        node = self._node(node_key)
        now = _now()
        node["status"] = "active"
        node["activity"] = activity
        node["started_at"] = node["started_at"] or _iso(now)
        if post_index is not None:
            self._item_started_at[(node_key, post_index)] = now
            total = int(total_posts or self.state.get("total_posts") or 0)
            node["total_items"] = total
            self.state["current_post"] = {
                "index": post_index,
                "total": total,
            }
        self.state["active_node"] = node_key
        self.state["status"] = "running"
        self._append_event(
            node_key,
            "active",
            activity,
            detail=detail,
            post_index=post_index,
            total_posts=total_posts,
            metadata=metadata,
        )
        self._persist(current_stage=current_stage or activity, status="generating")

    def complete(
        self,
        node_key: str,
        summary: str,
        *,
        current_stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        node = self._node(node_key)
        node["status"] = "completed"
        node["activity"] = summary
        node["output_summary"] = summary
        node["completed_at"] = _iso()
        if self.active_node == node_key:
            self.state["active_node"] = None
        self._append_event(node_key, "completed", summary, metadata=metadata)
        self._persist(current_stage=current_stage or summary)

    def item_complete(
        self,
        node_key: str,
        post_index: int,
        total_posts: int,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        node = self._node(node_key)
        node["completed_items"] = min(
            total_posts,
            int(node["completed_items"]) + 1,
        )
        node["total_items"] = total_posts
        node["activity"] = summary
        node["output_summary"] = summary
        finished = node["completed_items"] >= total_posts
        node["status"] = "completed" if finished else "waiting"
        if finished:
            node["completed_at"] = _iso()
        if self.active_node == node_key:
            self.state["active_node"] = None
        started = self._item_started_at.pop((node_key, post_index), None)
        duration_ms = None
        if started:
            duration_ms = max(0, round((_now() - started).total_seconds() * 1000))
        self._append_event(
            node_key,
            "completed",
            summary,
            post_index=post_index,
            total_posts=total_posts,
            metadata=metadata,
            duration_ms=duration_ms,
        )
        self._persist(current_stage=summary)

    def item_failed(
        self,
        node_key: str,
        post_index: int,
        total_posts: int,
        message: str,
    ) -> None:
        node = self._node(node_key)
        node["failed_items"] = int(node["failed_items"]) + 1
        node["status"] = "warning"
        node["activity"] = "تعذّر إكمال هذا المنشور؛ انتقل النظام للمنشور التالي."
        if self.active_node == node_key:
            self.state["active_node"] = None
        self.state["failed_posts"] = int(self.state.get("failed_posts") or 0) + 1
        self._append_event(
            node_key,
            "warning",
            "تعذّر إكمال منشور واحد",
            detail=message,
            post_index=post_index,
            total_posts=total_posts,
        )
        self._persist(current_stage=f"تعذّر المنشور {post_index} من {total_posts}")

    def post_saved(self, posts_generated: int, total_posts: int) -> None:
        self.state["posts_generated"] = max(
            int(self.state.get("posts_generated") or 0), posts_generated
        )
        self.state["current_post"] = {
            "index": min(posts_generated + 1, total_posts),
            "total": total_posts,
        }
        self._persist()

    def finish(
        self,
        *,
        posts_generated: int,
        total_posts: int,
        errors: list[str],
    ) -> None:
        partial = bool(errors) or posts_generated < total_posts
        for key in PRODUCTION_NODE_KEYS:
            node = self._node(key)
            if node["completed_items"] >= total_posts and total_posts:
                node["status"] = "completed"
                node["completed_at"] = node["completed_at"] or _iso()
            elif partial:
                node["status"] = "warning"

        scheduler = self._node("scheduler")
        scheduler["status"] = "waiting_approval"
        scheduler["activity"] = "بانتظار اعتمادك للمنشورات قبل الجدولة والنشر."
        scheduler["output_summary"] = "لن يُنشر أي شيء دون قرارك."

        self.state["status"] = "done_with_errors" if partial else "done"
        self.state["active_node"] = None
        self.state["overall_progress"] = 100
        self.state["posts_generated"] = posts_generated
        self.state["total_posts"] = total_posts
        self.state["current_post"] = None
        self.state["completed_at"] = _iso()
        self._append_event(
            "scheduler",
            "waiting_approval",
            "الحملة جاهزة لمراجعتك واعتماد المنشورات.",
            metadata={"posts_generated": posts_generated, "total_posts": total_posts},
        )
        # _persist normally caps running progress at 99; restore 100 afterwards.
        self._persist(
            status="done_with_errors" if partial else "done",
            current_stage=(
                "⚠️ اكتملت الحملة جزئياً مع أخطاء؛ راجع المنشورات المتاحة."
                if partial
                else "✅ اكتملت الحملة وأصبحت جاهزة للمراجعة."
            ),
            error_message=" | ".join(errors) if errors else None,
        )
        self.state["overall_progress"] = 100
        update_plan_generation_state(
            self.plan_id,
            pipeline_state=deepcopy(self.state),
        )

    def fail(self, message: str, *, current_stage: str | None = None) -> None:
        key = self.active_node or "orchestrator"
        node = self._node(key)
        node["status"] = "failed"
        node["activity"] = "توقّف التنفيذ عند هذه العقدة."
        node["output_summary"] = None
        self.state["status"] = "failed"
        self.state["error"] = message
        self.state["completed_at"] = _iso()
        self._append_event(key, "failed", "توقّف التنفيذ", detail=message)
        self._persist(
            status="failed",
            current_stage=current_stage or node["activity"],
            error_message=message,
        )
