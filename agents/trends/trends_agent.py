"""
Trends Agent — وكيل جلب التريندات/المواضيع الرائجة.

مربوط بالشات بوت عبر نية GET_TRENDS وبسياق الحملة (include_trends).
يولّد تريندات ذات صلة بمجال البراند عبر الـ LLM، مع قائمة احتياطية ثابتة
تضمن أن يعيد دائماً محتوى مفيداً (لا فراغ).
"""
from __future__ import annotations

from services.llm_service import call_llm_json


_TRENDS_PROMPT = """أنت خبير سوشيال ميديا يتابع المواضيع الرائجة في السوق العربي.
اقترح {limit} تريندات/مواضيع رائجة حالياً ومناسبة لمجال هذا النشاط:

مجال النشاط: {niche}

أعِد JSON فقط:
{{
  "trends": [
    {{
      "title": "عنوان الترند القصير",
      "description": "لماذا هو رائج وكيف يُستثمر تسويقياً بجملة",
      "hashtags": ["#هاشتاق1", "#هاشتاق2"],
      "score": 85
    }}
  ]
}}
قواعد: score رقم 0-100 يعكس قوة الرواج، والتريندات عملية وقابلة للاستخدام في منشور."""


# قائمة احتياطية عامة (تعمل دائماً بلا LLM)
_FALLBACK_TRENDS = [
    {"title": "المحتوى القصير (Reels)", "description": "الفيديوهات القصيرة تحقّق أعلى وصول وتفاعل حالياً.",
     "hashtags": ["#ريلز", "#reels"], "score": 92},
    {"title": "خلف الكواليس (Behind the Scenes)", "description": "إظهار كواليس العمل يبني ثقة وقرباً من الجمهور.",
     "hashtags": ["#خلف_الكواليس"], "score": 84},
    {"title": "آراء العملاء (UGC)", "description": "إعادة نشر محتوى العملاء يعزّز المصداقية والمبيعات.",
     "hashtags": ["#تجربتي", "#آراء_العملاء"], "score": 88},
    {"title": "العروض المحدودة", "description": "الندرة والوقت المحدود يحفّزان الشراء الفوري.",
     "hashtags": ["#عرض_محدود", "#خصومات"], "score": 80},
    {"title": "الأسئلة والاستطلاعات", "description": "المحتوى التفاعلي يرفع الوصول عبر خوارزميات فيسبوك.",
     "hashtags": ["#استطلاع"], "score": 78},
]


def fetch_trends(niche: str = "", limit: int = 5) -> dict:
    """
    يُرجع تريندات رائجة ذات صلة بالمجال.
      إن توفّر niche → يولّدها الـ LLM؛ وإلا/عند الفشل → القائمة الاحتياطية.
    """
    trends: list[dict] = []
    if niche and niche.strip():
        try:
            res = call_llm_json(_TRENDS_PROMPT.format(niche=niche.strip(), limit=limit))
            trends = res.get("trends", []) if isinstance(res, dict) else []
        except Exception:  # noqa: BLE001
            trends = []

    if not trends:
        trends = _FALLBACK_TRENDS[:limit]

    return {
        "niche": niche,
        "trends": trends,
        "placeholder": False,
        "note": "أبرز التريندات الرائجة المقترحة" + (f" لمجال: {niche}" if niche else ""),
    }
