"""
المصدر الوحيد للحقيقة (Single Source of Truth) لإطار التقييم.

كل بُعد له: المفتاح، الاسم، الطبقة، الوزن، طريقة القياس، وهل هو بوابة.
مجموع أوزان الأبعاد العادية = 100  ⇒  الناتج نسبة مئوية مباشرة.

طرق القياس:
  rule  → فحص حتمي قاعدي (بدون نموذج)        ← متوفّر في المرحلة 1
  judge → حَكَم لغوي (Gemini)                  ← المرحلة 2
  human → مراجعة بشرية على عيّنة               ← المرحلة 3
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    key: str
    name_ar: str
    layer: str        # "A" | "B" | "C"
    weight: int
    method: str       # "rule" | "judge" | "human"


# ── الأبعاد الموزونة (المجموع = 100) ─────────────────────────────────────────
DIMENSIONS: list[Dimension] = [
    # الطبقة A — جودة المخرَج (60)
    Dimension("brand_voice",  "توافق صوت البراند",      "A", 10, "judge"),
    Dimension("engagement",   "احتمالية التفاعل",        "A",  8, "judge"),
    Dimension("platform",     "التكيّف مع المنصة",       "A",  8, "rule"),
    Dimension("cta",          "الدعوة للتفاعل (CTA)",    "A",  7, "rule"),
    Dimension("clarity",      "الوضوح",                  "A",  7, "rule"),
    Dimension("tone",         "ملاءمة النبرة",           "A",  6, "judge"),
    Dimension("emotion",      "الجاذبية العاطفية",       "A",  6, "judge"),
    Dimension("creativity",   "الإبداع والأصالة",        "A",  4, "judge"),
    Dimension("grammar",      "سلامة اللغة",             "A",  4, "rule"),
    # الطبقة B — سلوك الوكيل (25)
    Dimension("tcr",          "نسبة إكمال المهمة",       "B",  8, "rule"),
    Dimension("efficiency",   "التكلفة والكفاءة",        "B",  5, "rule"),
    Dimension("tool_osr",     "نظافة الأدوات (OSR)",     "B",  4, "rule"),
    Dimension("planning",     "جودة التخطيط",            "B",  4, "judge"),
    Dimension("multiturn",    "الاتساق متعدد الجولات",   "B",  4, "judge"),
    # الطبقة C — المتانة (15)
    Dimension("stability",    "ثبات المخرَج",            "C",  6, "rule"),
    Dimension("transfer",     "الانتقال عبر المجال",     "C",  5, "judge"),
    Dimension("adversarial",  "مقاومة التشويش",          "C",  4, "rule"),
]

assert sum(d.weight for d in DIMENSIONS) == 100, "أوزان الأبعاد يجب أن تساوي 100"

LAYERS = {"A": "جودة المخرَج", "B": "سلوك الوكيل", "C": "المتانة"}

# ── البوابات الحرجة (تمرير / رسوب — خارج الوزن) ──────────────────────────────
GATES = [
    {"key": "safety",  "name_ar": "الأمان والامتثال", "method": "rule",  "on_fail": "reject"},
    {"key": "spam",    "name_ar": "السبام والجودة",   "method": "rule",  "on_fail": "cap50"},
    {"key": "factual", "name_ar": "الدقة المعرفية",   "method": "human", "on_fail": "cap50"},
]

# ── نطاقات تفسير النسبة ──────────────────────────────────────────────────────
BANDS = [
    (90, "ممتاز — جاهز للنشر مباشرة",        "#36d399"),
    (80, "جيد جداً — قابل للنشر بمراجعة طفيفة", "#7fce5a"),
    (65, "مقبول — يحتاج تعديلاً بشرياً",      "#fbbd23"),
    (50, "ضعيف — إعادة توليد",               "#fb923c"),
    (0,  "مرفوض — لا يُنشر",                  "#f87272"),
]


def band_for(pct: float) -> tuple[str, str]:
    """يرجع (الوصف، اللون) للنسبة المئوية."""
    for threshold, label, color in BANDS:
        if pct >= threshold:
            return label, color
    return BANDS[-1][1], BANDS[-1][2]


# ── معايير كل منصة (تُستخدم في الفحوصات القاعدية) ────────────────────────────
PLATFORMS = {
    "facebook":  {"len_ideal": (80, 600),  "len_max": 2000, "tags_ideal": (0, 3),  "tags_max": 5},
    "instagram": {"len_ideal": (50, 400),  "len_max": 2200, "tags_ideal": (3, 11), "tags_max": 30},
    "twitter":   {"len_ideal": (20, 240),  "len_max": 280,  "tags_ideal": (0, 2),  "tags_max": 3},
    "x":         {"len_ideal": (20, 240),  "len_max": 280,  "tags_ideal": (0, 2),  "tags_max": 3},
    "linkedin":  {"len_ideal": (100, 700), "len_max": 3000, "tags_ideal": (0, 5),  "tags_max": 8},
}
DEFAULT_PLATFORM = "facebook"


def platform_spec(platform: str) -> dict:
    return PLATFORMS.get((platform or "").lower().strip(), PLATFORMS[DEFAULT_PLATFORM])
