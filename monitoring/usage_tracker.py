"""
طبقة المراقبة (Monitoring / Observability Layer) — البند 5.16.11 و5.16.12.

تتوسط بين الوكلاء وخدمة الذكاء الاصطناعي دون أن يحتاج كل وكيل لكتابة
منطق مراقبة مستقل:

    Agent → Monitoring Layer → AI Model → Monitoring Layer → Agent

تُستخدم عبر context manager `track_llm_call(...)` حول كل استدعاء فعلي
لنموذج الذكاء الاصطناعي في services/llm_service.py، وتسجّل كل عملية
كصف في جدول llm_usage_logs (Trace/Span، Tokens، الزمن، التكلفة، الحالة).

trace_id يمثل دورة تنفيذ حملة كاملة، وspan_id يمثل استدعاء وكيل واحد
ضمنها. عند تنفيذ خارج سياق حملة (مثل المحادثة الحرة) يُنشأ trace خاص
بالطلب نفسه.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from uuid import uuid4

from monitoring.pricing import calculate_cost

# سياق التتبّع الحالي (trace_id, user_id, content_plan_id) — يُضبط من نقطة
# الدخول (مثل بداية تنفيذ حملة) وتقرأه كل استدعاءات call_llm تلقائياً
# دون تمرير معاملات إضافية عبر كل طبقات الوكلاء.
_current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_current_user_id: ContextVar[int | None] = ContextVar("user_id", default=None)
_current_content_plan_id: ContextVar[int | None] = ContextVar("content_plan_id", default=None)
_current_agent_name: ContextVar[str] = ContextVar("agent_name", default="unknown_agent")


def new_trace_id() -> str:
    return f"trace_{uuid4().hex[:16]}"


@contextmanager
def trace_context(user_id: int | None = None, content_plan_id: int | None = None, trace_id: str | None = None):
    """يفتح دورة تنفيذ (Trace) جديدة — تُستخدم عند بدء حملة أو محادثة."""
    tid = trace_id or new_trace_id()
    t_tok = _current_trace_id.set(tid)
    u_tok = _current_user_id.set(user_id)
    c_tok = _current_content_plan_id.set(content_plan_id)
    try:
        yield tid
    finally:
        _current_trace_id.reset(t_tok)
        _current_user_id.reset(u_tok)
        _current_content_plan_id.reset(c_tok)


@contextmanager
def agent_context(agent_name: str):
    """يحدد اسم الوكيل المسؤول عن استدعاءات call_llm التالية ضمن هذا الـ block."""
    tok = _current_agent_name.set(agent_name)
    try:
        yield
    finally:
        _current_agent_name.reset(tok)


RETRYABLE_ERROR_TYPES = {"RateLimitError", "ServiceUnavailable", "TimeoutError", "ConnectionError"}


def classify_error(exc: Exception) -> str:
    msg = str(exc)
    if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg.lower():
        return "ServiceUnavailable"
    if "429" in msg or "rate limit" in msg.lower():
        return "RateLimitError"
    if "401" in msg or "403" in msg or "permission" in msg.lower():
        return "PermissionError"
    if "400" in msg or "invalid" in msg.lower():
        return "ValidationError"
    return type(exc).__name__


@contextmanager
def track_llm_call(model_name: str, agent_name: str | None = None):
    """يحيط استدعاءً واحداً للنموذج ويسجّله في llm_usage_logs عند الخروج.

    الاستخدام (داخل services/llm_service.py):

        with track_llm_call(model_name=settings.GEMINI_MODEL) as usage:
            response = _client.models.generate_content(...)
            usage.set_tokens(input_tokens, output_tokens)

    عند حدوث استثناء، يُسجَّل الفشل تلقائياً (status="failed") مع نوع
    الخطأ، ثم يُعاد رفع الاستثناء دون تغيير سلوك الوكيل المستدعي.
    """
    span_id = f"span_{uuid4().hex[:16]}"
    trace_id = _current_trace_id.get() or new_trace_id()
    resolved_agent = agent_name or _current_agent_name.get()

    usage = _PendingUsage(
        trace_id=trace_id,
        span_id=span_id,
        agent_name=resolved_agent,
        model_name=model_name,
        user_id=_current_user_id.get(),
        content_plan_id=_current_content_plan_id.get(),
    )
    start = time.perf_counter()
    started_at = datetime.utcnow()

    try:
        yield usage
        duration_ms = (time.perf_counter() - start) * 1000
        usage.finalize(started_at=started_at, duration_ms=duration_ms, status="success")
        _persist(usage)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        usage.finalize(
            started_at=started_at,
            duration_ms=duration_ms,
            status="failed",
            error_type=classify_error(exc),
        )
        _persist(usage)
        raise


class _PendingUsage:
    """كائن مؤقت يجمع بيانات الاستدعاء أثناء تنفيذه، قبل تحويله لسجل DB."""

    def __init__(self, trace_id, span_id, agent_name, model_name, user_id, content_plan_id):
        self.trace_id = trace_id
        self.span_id = span_id
        self.agent_name = agent_name
        self.model_name = model_name
        self.user_id = user_id
        self.content_plan_id = content_plan_id
        self.input_tokens = 0
        self.output_tokens = 0
        self.retry_count = 0
        self.started_at = None
        self.completed_at = None
        self.duration_ms = 0.0
        self.status = "success"
        self.error_type = None
        self.estimated_cost = 0.0

    def set_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens or 0
        self.output_tokens = output_tokens or 0

    def add_retry(self) -> None:
        self.retry_count += 1

    def finalize(self, started_at, duration_ms, status, error_type=None) -> None:
        self.started_at = started_at
        self.completed_at = datetime.utcnow()
        self.duration_ms = duration_ms
        self.status = status
        self.error_type = error_type
        self.estimated_cost = calculate_cost(self.input_tokens, self.output_tokens, self.model_name)


def _persist(usage: _PendingUsage) -> None:
    """يخزّن سجل الاستهلاك في قاعدة البيانات الرئيسية للنظام."""
    # استيراد مؤخّر لتفادي any circular-import بين monitoring وdatabase عند الإقلاع
    from database.models import LLMUsageLog
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        row = LLMUsageLog(
            trace_id=usage.trace_id,
            span_id=usage.span_id,
            user_id=usage.user_id,
            content_plan_id=usage.content_plan_id,
            agent_name=usage.agent_name,
            model_name=usage.model_name,
            started_at=usage.started_at,
            completed_at=usage.completed_at,
            duration_ms=usage.duration_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
            estimated_cost=usage.estimated_cost,
            status=usage.status,
            retry_count=usage.retry_count,
            error_type=usage.error_type,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        # لا نُفشل تنفيذ الوكيل بسبب خطأ في تسجيل المراقبة نفسها
    finally:
        db.close()
