"""
محرّك التسجيل: يجمع درجات الأبعاد، يطبّق البوابات، ويحسب النسبة المئوية.

المعادلة:  Score(%) = Σ ( score_i / 5 × weight_i )   ← معدّلة بالبوابات

في المرحلة 1 نسجّل الأبعاد القاعدية فقط؛ الأبعاد الأخرى تبقى "معلّقة" (pending)
حتى المرحلة 2 (الحَكَم اللغوي). لذلك نُبلّغ نتيجتين بصدق:
  • coverage_pct   = نسبة الوزن المُقيَّم آلياً حتى الآن
  • provisional_pct = النسبة على الأبعاد المُقيَّمة (تُطبَّع على وزنها)
"""
from __future__ import annotations

from evaluation.rubric import DIMENSIONS, GATES, band_for
from evaluation.rule_checks import RULE_SCORERS, GATE_CHECKERS


def evaluate_post(post: dict, brand: dict | None = None, judge=None) -> dict:
    """
    قيّم منشوراً واحداً.
      post  : قاموس المنشور (hook/caption/cta/hashtags...)
      brand : إرشادات البراند (must_use_words/forbidden_words/preferred_cta)
      judge : دالة اختيارية للحَكَم اللغوي judge(dim_key, post, brand)->(score,note)
              (المرحلة 2). إن كانت None تبقى أبعاد الحَكَم معلّقة.
    """
    brand = brand or {}
    dims_out = []
    earned = 0.0           # مجموع المساهمات للأبعاد المُقيَّمة
    covered_weight = 0.0   # مجموع أوزان الأبعاد المُقيَّمة

    for d in DIMENSIONS:
        score = None
        note = "معلّق — يحتاج المرحلة التالية"
        status = "pending"

        if d.method == "rule" and d.key in RULE_SCORERS:
            score, note = RULE_SCORERS[d.key](post, brand)
            status = "scored"
        elif d.method == "judge" and judge is not None:
            res = judge(d.key, post, brand)
            if res is not None:
                score, note = res
                status = "scored"

        contribution = (score / 5.0 * d.weight) if score is not None else 0.0
        if status == "scored":
            earned += contribution
            covered_weight += d.weight

        dims_out.append({
            "key": d.key, "name": d.name_ar, "layer": d.layer, "method": d.method,
            "weight": d.weight, "score": score, "contribution": round(contribution, 2),
            "note": note, "status": status,
        })

    # ── البوابات ─────────────────────────────────────────────────────────────
    gates_out = []
    cap = None            # سقف على النسبة (مثلاً 50)
    rejected = False
    for g in GATES:
        if g["key"] in GATE_CHECKERS:
            gstatus, gnote = GATE_CHECKERS[g["key"]](post, brand)
        else:
            gstatus, gnote = "pending", "يحتاج مراجعة بشرية (المرحلة 3)"
        if gstatus == "fail":
            if g["on_fail"] == "reject":
                rejected = True
            elif g["on_fail"] == "cap50":
                cap = 50
        gates_out.append({"key": g["key"], "name": g["name_ar"],
                          "status": gstatus, "note": gnote})

    # ── الحساب النهائي ───────────────────────────────────────────────────────
    coverage_pct = round(covered_weight, 1)                       # من 100
    provisional_pct = round(earned / covered_weight * 100, 1) if covered_weight else 0.0

    final_status = "passed"
    effective_pct = provisional_pct
    if rejected:
        final_status = "REJECTED — رسوب بوابة الأمان"
        effective_pct = 0.0
    elif cap is not None and provisional_pct > cap:
        final_status = f"capped — مسقوف عند {cap}% بسبب بوابة"
        effective_pct = float(cap)

    band_label, band_color = band_for(effective_pct)

    return {
        "post": post,
        "dimensions": dims_out,
        "gates": gates_out,
        "coverage_pct": coverage_pct,         # كم % من الوزن مُقيَّم آلياً
        "provisional_pct": provisional_pct,   # النسبة على المُقيَّم (مُطبَّعة)
        "effective_pct": effective_pct,       # بعد البوابات
        "final_status": final_status,
        "band_label": band_label,
        "band_color": band_color,
        "complete": covered_weight >= 100,    # هل اكتمل التقييم الكامل؟
    }
