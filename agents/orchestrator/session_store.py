"""
مخزن الجلسات في الذاكرة — يحفظ حالة الحوار بين كل رسالة والأخرى.
(كافٍ لمشروع التخرج والعرض؛ يمكن ترقيته لجدول DB لاحقاً بلا تغيير الواجهة.)

كل جلسة تحفظ:
  intent   : النية الحالية قيد التنفيذ (أو None)
  slots    : المعلومات المجمّعة (product_id, days, review_text, ...)
  awaiting : اسم الحقل الذي ننتظر إجابة المستخدم عنه (أو None)
  options  : آخر خيارات عُرضت (لتفسير ردّ المستخدم برقم)
  history  : سجل الحوار [(role, text), ...]
  cache    : تخزين مؤقت (مثل brand_guidelines) لتقليل استدعاءات LLM
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    intent: str | None = None
    slots: dict = field(default_factory=dict)
    awaiting: str | None = None
    options: list = field(default_factory=list)
    history: list = field(default_factory=list)
    cache: dict = field(default_factory=dict)

    def clear_task(self) -> None:
        """ينهي المهمة الحالية ويُبقي التاريخ والكاش."""
        self.intent = None
        self.slots = {}
        self.awaiting = None
        self.options = []


_SESSIONS: dict[str, Session] = {}


def get_or_create(session_id: str | None) -> Session:
    if session_id and session_id in _SESSIONS:
        return _SESSIONS[session_id]
    sid = session_id or uuid.uuid4().hex[:12]
    s = Session(id=sid)
    _SESSIONS[sid] = s
    return s


def get(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def reset(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)
