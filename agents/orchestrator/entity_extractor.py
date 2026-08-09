"""
Step 2 — مستخرِج الكيانات (Entity Extractor).
النظام مخصّص لفيسبوك فقط — لا استخراج/اختيار منصة.
يستخرج: المنتج، الأيام، نوع المنشور، ونص المراجعة. LLM أولاً مع بديل قاعدي.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_POST_TYPES = {
    "promotional": ["ترويج", "ترويجي", "عرض", "خصم"],
    "educational": ["تعليمي", "معلومة", "شرح"],
    "engagement": ["تفاعل", "سؤال", "استطلاع"],
}


def detect_days(text: str) -> int | None:
    if "أسبوع" in text or "اسبوع" in text or "week" in text.lower():
        return 7
    if "شهر" in text or "month" in text.lower():
        return 30
    m = re.search(r"(\d+)\s*(?:يوم|أيام|ايام|days?)", text.lower())
    if m:
        return int(m.group(1))
    return None


def _detect_product_name(text: str) -> str | None:
    # أنماط شائعة: "عن X" / "لمنتج X" / "منتج X" / "للـ X"
    for pat in [r"عن\s+(.+)", r"لمنتج\s+(.+)", r"منتج\s+(.+)", r"للـ?\s*(.+)"]:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip(" .،؟!\"'")
            name = re.split(r"\s+(?:على|في|بمنصة)", name)[0].strip()
            if 1 <= len(name) <= 60:
                return name
    return None


def parse_schedule_time(text: str) -> str | None:
    """يحوّل تعبير وقت عربي/تاريخ إلى ISO (YYYY-MM-DDTHH:MM) أو None."""
    t = text.strip()
    now = datetime.now()

    # تاريخ صريح: 2026-08-05 أو 2026-08-05 18:00
    m = re.search(r"(\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?)", t)
    if m:
        try:
            return datetime.fromisoformat(m.group(1).replace(" ", "T")).isoformat(timespec="minutes")
        except ValueError:
            pass

    hour_m = re.search(r"الساعة\s*(\d{1,2})", t)
    hour = int(hour_m.group(1)) if hour_m else None

    if "بعد ساعتين" in t:
        return (now + timedelta(hours=2)).isoformat(timespec="minutes")
    mh = re.search(r"بعد\s*(\d+)\s*ساعة", t)
    if mh:
        return (now + timedelta(hours=int(mh.group(1)))).isoformat(timespec="minutes")
    if "بعد ساعة" in t:
        return (now + timedelta(hours=1)).isoformat(timespec="minutes")

    base = None
    if any(k in t for k in ["غدا", "غداً", "بكرا", "بكره", "غد "]):
        base = now + timedelta(days=1)
    elif "بعد يومين" in t:
        base = now + timedelta(days=2)
    elif "بعد يوم" in t:
        base = now + timedelta(days=1)
    elif "اليوم" in t:
        base = now
    if base is not None:
        return base.replace(hour=hour if hour is not None else 10,
                            minute=0, second=0, microsecond=0).isoformat(timespec="minutes")
    return None


def _detect_post_type(text: str) -> str | None:
    for canon, kws in _POST_TYPES.items():
        if any(kw in text for kw in kws):
            return canon
    return None


def _rule_extract(message: str) -> dict:
    return {
        "product_name": _detect_product_name(message),
        "days": detect_days(message),
        "post_type": _detect_post_type(message),
        "schedule_time": parse_schedule_time(message),
        "review_text": None,
    }


def extract_entities(message: str, use_llm: bool = True) -> dict:
    base = _rule_extract(message)
    if use_llm:
        try:
            from services.llm_service import call_llm_json
            from prompts.orchestrator_prompts import ENTITY_EXTRACTION_PROMPT
            res = call_llm_json(ENTITY_EXTRACTION_PROMPT.format(message=message))
            for k in base:
                v = res.get(k)
                if v not in (None, "", "null"):
                    base[k] = v
        except Exception:  # noqa: BLE001
            pass
    return base
