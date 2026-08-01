"""
تشغيل تجريبي للمرحلة 1 — يعمل فوراً وبدون أي نموذج أو اتصال.

    python -m evaluation.demo_eval

ينتج: ملخّصاً في الطرفية + ملف evaluation_report.html يُفتح في المتصفح.
"""
from __future__ import annotations

import sys

# ضمان طباعة العربية على طرفية ويندوز (cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from evaluation.scorer import evaluate_post
from evaluation.report import save_report

# ── منشور تجريبي بنفس بنية مخرجات وكيلك ──────────────────────────────────────
SAMPLE_POST = {
    "post_type": "promotional",
    "goal": "زيادة المبيعات",
    "hook": "صباحك أحلى مع قهوتنا المختصة ☕",
    "caption": (
        "بنحمّص حبوب القهوة كل صباح لنقدّم لك فنجاناً بنكهة لا تُقاوم. "
        "جرّب مزيجنا الجديد اليوم وشاركنا رأيك في التعليقات!"
    ),
    "cta": "اطلب الآن من المتجر",
    "hashtags": ["#قهوة_مختصة", "#صباح_الخير"],
}

SAMPLE_BRAND = {
    "must_use_words": ["قهوة مختصة"],
    "forbidden_words": ["رخيص", "مجاناً"],
    "preferred_cta": "اطلب الآن",
}


def main() -> None:
    result = evaluate_post(SAMPLE_POST, SAMPLE_BRAND)   # المرحلة 1: قاعدي فقط

    print("=" * 56)
    print(f"  النسبة الفعّالة : {result['effective_pct']}%  ({result['band_label']})")
    print(f"  الحالة         : {result['final_status']}")
    print(f"  التغطية الآلية : {result['coverage_pct']}% من الوزن الكلّي")
    print("=" * 56)
    print("\n  الأبعاد المُقيَّمة:")
    for d in result["dimensions"]:
        if d["status"] == "scored":
            print(f"    • {d['name']:<22} {d['score']}/5  →  {d['note']}")
    print("\n  البوابات:")
    for g in result["gates"]:
        print(f"    • {g['name']:<22} [{g['status']}]  {g['note']}")

    path = save_report(result, "evaluation_report.html")
    print(f"\n  ✅ التقرير الكامل: {path}  (افتحيه في المتصفح)\n")


if __name__ == "__main__":
    main()
