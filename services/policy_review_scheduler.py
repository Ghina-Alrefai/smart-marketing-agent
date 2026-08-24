"""Lightweight daily trigger for the evidence-driven monthly policy review.

The review due date lives in SQLite, so restarts do not reset the schedule. For a
multi-worker production deployment this trigger should be replaced by one queue
worker/cron job; the review engine and API remain unchanged.
"""
from __future__ import annotations

import asyncio
import logging

from config import settings
from services.brand_intelligence_service import memory_service


logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _run_once() -> None:
    result = await asyncio.to_thread(
        memory_service().review_due_policies,
        reviewed_by="policy-review-scheduler",
    )
    if result.reviewed_policy_count or result.expired_without_review_count:
        logger.info(
            "policy_review.completed reviewed=%s expired_without_review=%s decisions=%s",
            result.reviewed_policy_count,
            result.expired_without_review_count,
            result.decision_counts,
        )


async def _scheduler_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            await _run_once()
        except Exception:  # noqa: BLE001 - scheduler must not stop the API process
            logger.exception("policy_review.scheduler_failed")
        try:
            await asyncio.wait_for(
                _stop_event.wait(),
                timeout=max(60, settings.POLICY_REVIEW_CHECK_INTERVAL_SECONDS),
            )
        except asyncio.TimeoutError:
            continue


def start_policy_review_scheduler() -> None:
    global _task, _stop_event
    if not settings.POLICY_REVIEW_ENABLED or (_task and not _task.done()):
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_scheduler_loop(), name="policy-review-scheduler")
    logger.info(
        "policy_review.scheduler_started check_interval_seconds=%s review_interval_days=%s",
        settings.POLICY_REVIEW_CHECK_INTERVAL_SECONDS,
        settings.POLICY_REVIEW_INTERVAL_DAYS,
    )


async def stop_policy_review_scheduler() -> None:
    global _task, _stop_event
    if _task is None:
        return
    if _stop_event is not None:
        _stop_event.set()
    await _task
    _task = None
    _stop_event = None
