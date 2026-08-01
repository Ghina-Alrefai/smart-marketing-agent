"""
الفحوصات القاعدية الحتمية (Rule-based) — بدون أي نموذج تعلُّم آلي.

كل دالة تستقبل (post, brand) وتُرجع (score: float 0-5, note: str).
نفس المدخل يعطي نفس النتيجة دائماً ⇒ قابلية إعادة إنتاج 100%.

البنية المتوقعة:
  post  = {"hook","caption","cta","hashtags":[...],"post_type","goal"}
  brand = {"must_use_words":[...],"forbidden_words":[...],"preferred_cta": "..."}
"""
from __future__ import annotations

import re

from evaluation.rubric import FACEBOOK_SPEC

# قائمة أفعال الدعوة للتفاعل بالعربية (تُوسَّع حسب الحاجة)
CTA_KEYWORDS = [
    "اطلب", "اطلبي", "احجز", "احجزي", "تسوق", "تسوّق", "اشترِ", "اشتري",
    "سجّل", "سجل", "تابعنا", "تابع", "شارك", "شاركنا", "علّق", "علق",
    "اكتب رأيك", "زورونا", "زورنا", "اتصل", "تواصل", "احصل", "جرّب", "جرب",
    "انضم", "لا تفوت", "لا تفوّت", "اكتشف", "حمّل", "حمل", "استفد",
]

# علامات السبام
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
URL_RE = re.compile(r"https?://|www\.")
REPEATED_CHAR_RE = re.compile(r"(.)\1{3,}")          # ههههه، !!!!، ....
SENTENCE_SPLIT_RE = re.compile(r"[.!؟\n]+")


# ── أدوات مساعدة ─────────────────────────────────────────────────────────────
def _full_text(post: dict) -> str:
    parts = [post.get("hook", ""), post.get("caption", ""), post.get("cta", "")]
    tags = post.get("hashtags") or []
    if isinstance(tags, list):
        parts.append(" ".join(str(t) for t in tags))
    return " ".join(p for p in parts if p).strip()


def _clamp(x: float, lo: float = 0.0, hi: float = 5.0) -> float:
    return max(lo, min(hi, x))


# ── الأبعاد القاعدية ─────────────────────────────────────────────────────────
def check_cta(post: dict, brand: dict) -> tuple[float, str]:
    text = (post.get("cta", "") + " " + post.get("caption", "")).strip()
    if not text:
        return 0.0, "لا يوجد نص CTA إطلاقاً"
    preferred = (brand.get("preferred_cta") or "").strip()
    if preferred and preferred in text:
        return 5.0, f"يستخدم CTA المفضّل للبراند: «{preferred}»"
    hits = [k for k in CTA_KEYWORDS if k in text]
    if hits:
        return 4.0, f"يحتوي دعوة للتفاعل ({hits[0]}) لكن ليست CTA المفضّلة"
    return 1.0, "لا توجد دعوة واضحة للتفاعل"


def check_fb_fit(post: dict, brand: dict) -> tuple[float, str]:
    spec = FACEBOOK_SPEC
    text = _full_text(post)
    n = len(text)
    tags = post.get("hashtags") or []
    n_tags = len(tags) if isinstance(tags, list) else 0

    # درجة الطول
    lo, hi = spec["len_ideal"]
    if lo <= n <= hi:
        len_score = 5.0
    elif n > spec["len_max"]:
        len_score = 1.0
    elif n > hi:
        len_score = 3.0
    else:  # أقصر من المثالي
        len_score = 2.5

    # درجة الهاشتاق
    t_lo, t_hi = spec["tags_ideal"]
    if t_lo <= n_tags <= t_hi:
        tag_score = 5.0
    elif n_tags > spec["tags_max"]:
        tag_score = 1.5
    else:
        tag_score = 3.5

    score = round((len_score * 0.7 + tag_score * 0.3), 2)
    return score, f"الطول {n} حرف، {n_tags} هاشتاق (مثالي {lo}-{hi} حرف / {t_lo}-{t_hi} وسم)"


def check_clarity(post: dict, brand: dict) -> tuple[float, str]:
    caption = post.get("caption", "").strip()
    if not caption:
        return 1.0, "لا يوجد نص أساسي"
    sentences = [s for s in SENTENCE_SPLIT_RE.split(caption) if s.strip()]
    if not sentences:
        return 2.0, "نص بلا فواصل واضحة"
    avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
    if avg_words <= 15:
        score = 5.0
    elif avg_words <= 22:
        score = 4.0
    elif avg_words <= 30:
        score = 3.0
    else:
        score = 2.0
    return score, f"متوسط {avg_words:.1f} كلمة/جملة ({len(sentences)} جُمل)"


def check_grammar(post: dict, brand: dict) -> tuple[float, str]:
    """مؤشّر قاعدي (Proxy) — ليس تدقيقاً نحوياً كاملاً (انظر المرحلة 2)."""
    text = _full_text(post)
    if not text:
        return 0.0, "نص فارغ"
    score = 5.0
    notes = []
    rep = len(REPEATED_CHAR_RE.findall(text))
    if rep:
        score -= min(2.0, rep * 0.5)
        notes.append(f"{rep} تكرار حروف/رموز")
    excl = text.count("!") + text.count("؟؟")
    if excl > 3:
        score -= 1.0
        notes.append(f"{excl} علامات تعجب/استفهام زائدة")
    words = text.split()
    dup_adj = sum(1 for i in range(1, len(words)) if words[i] == words[i - 1])
    if dup_adj:
        score -= min(1.5, dup_adj * 0.5)
        notes.append(f"{dup_adj} كلمات مكرّرة متجاورة")
    return _clamp(score), "؛ ".join(notes) if notes else "لا مشاكل سطحية واضحة"


def check_tcr(post: dict, brand: dict) -> tuple[float, str]:
    """نسبة إكمال المهمة (Proxy من المنشور): هل أُنتجت كل الحقول المطلوبة؟"""
    required = {"hook": post.get("hook"), "caption": post.get("caption"), "cta": post.get("cta")}
    has_tags = bool(post.get("hashtags"))
    produced = sum(1 for v in required.values() if (v or "").strip()) + (1 if has_tags else 0)
    total = len(required) + 1
    score = round(produced / total * 5, 2)
    missing = [k for k, v in required.items() if not (v or "").strip()]
    if not has_tags:
        missing.append("hashtags")
    note = "كل الحقول مكتملة" if not missing else f"حقول ناقصة: {', '.join(missing)}"
    return score, note


# ── البوابات الحرجة ──────────────────────────────────────────────────────────
def gate_safety(post: dict, brand: dict) -> tuple[str, str]:
    text = _full_text(post)
    forbidden = [w for w in (brand.get("forbidden_words") or []) if w and w in text]
    if forbidden:
        return "fail", f"يحتوي كلمات محظورة من البراند: {', '.join(forbidden)}"
    return "pass", "خالٍ من الكلمات المحظورة"


def gate_spam(post: dict, brand: dict) -> tuple[str, str]:
    text = _full_text(post)
    spec = FACEBOOK_SPEC
    tags = post.get("hashtags") or []
    n_tags = len(tags) if isinstance(tags, list) else 0
    signals = []
    if len(EMOJI_RE.findall(text)) > 8:
        signals.append("إيموجي مفرط")
    if text.count("!") > 5:
        signals.append("علامات تعجب مفرطة")
    if len(URL_RE.findall(text)) > 2:
        signals.append("روابط متعددة")
    if n_tags > spec["tags_max"]:
        signals.append(f"هاشتاق مفرط ({n_tags})")
    if REPEATED_CHAR_RE.search(text):
        signals.append("تكرار رموز")
    if len(signals) >= 2:
        return "fail", "علامات سبام: " + "، ".join(signals)
    return "pass", ("ملاحظات بسيطة: " + "، ".join(signals)) if signals else "نظيف"


# ── خرائط التوزيع ────────────────────────────────────────────────────────────
RULE_SCORERS = {
    "fb_fit": check_fb_fit,
    "cta": check_cta,
    "clarity": check_clarity,
    "grammar": check_grammar,
    "tcr": check_tcr,
}

GATE_CHECKERS = {
    "safety": gate_safety,
    "spam": gate_spam,
}
