"""
Orchestrator Agent — طبقة chat ذكية فوق نظام الوكلاء.

بوابة واحدة تفهم طلب المستخدم بلغة طبيعية، توجّهه للوكيل/المسار المناسب،
وتحاوره لطلب أي معلومة ناقصة. لا تُعدّل نظام الـ Pipeline إطلاقاً — تستدعيه فقط.
"""
from agents.orchestrator.orchestrator_agent import handle_message  # noqa: F401
