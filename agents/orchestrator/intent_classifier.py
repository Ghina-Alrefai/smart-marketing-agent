"""
Step 1 — مصنّف النية (Intent Classifier).
يحاول عبر LLM، ويسقط لبديل قاعدي بالكلمات المفتاحية إن تعذّر — فيبقى صامداً.
"""
from __future__ import annotations

import re

INTENTS = [
    "WRITE_POST", "CREATE_DESIGN", "WRITE_AND_DESIGN",
    "REVIEW", "GET_STRATEGY", "FULL_PIPELINE", "UNKNOWN",
]

_DESIGN = ["صمم", "صمّم", "تصميم", "صورة", "ديزاين", "design", "بصري"]
_WRITE = ["اكتب", "أكتب", "منشور", "بوست", "كابشن", "caption", "محتوى", "نص ترويجي"]
_REVIEW = ["راجع", "مراجعة", "قيّم", "قيم", "تقييم", "review", "دقق"]
_STRATEGY = ["أفضل منتج", "افضل منتج", "شو أنشر", "شو انشر", "استراتيجية",
             "استراتيجيه", "اقتراح", "نصيحة", "ماذا أنشر"]
_PIPELINE = ["خطة", "حملة", "جدول", "calendar", "plan"]
_DURATION = ["أسبوع", "اسبوع", "شهر", "يوم", "أيام", "ايام", "days", "week", "month"]


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _rule_classify(message: str) -> str:
    t = message.lower()
    has_duration = _has(t, _DURATION) or bool(re.search(r"\d+", t))
    if _has(t, _REVIEW):
        return "REVIEW"
    if _has(t, _PIPELINE) and has_duration:
        return "FULL_PIPELINE"
    if _has(t, _DESIGN) and _has(t, _WRITE):
        return "WRITE_AND_DESIGN"
    if _has(t, _DESIGN):
        return "CREATE_DESIGN"
    if _has(t, _WRITE):
        return "WRITE_POST"
    if _has(t, _STRATEGY):
        return "GET_STRATEGY"
    if _has(t, _PIPELINE):
        return "FULL_PIPELINE"
    return "UNKNOWN"


def classify_intent(message: str, use_llm: bool = True) -> tuple[str, str]:
    """يرجع (intent, method) حيث method ∈ {"llm","rule"}."""
    if use_llm:
        try:
            from services.llm_service import call_llm_json
            from prompts.orchestrator_prompts import INTENT_CLASSIFIER_PROMPT
            res = call_llm_json(INTENT_CLASSIFIER_PROMPT.format(message=message))
            intent = res.get("intent", "")
            if intent in INTENTS:
                return intent, "llm"
        except Exception:  # noqa: BLE001
            pass
    return _rule_classify(message), "rule"
