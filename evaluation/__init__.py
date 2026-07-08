"""
Content-Generation Agent Evaluation Framework (المرحلة 1: المحرك القاعدي).

إطار تقييم متعدد الأبعاد يحوّل منشوراً مولَّداً إلى نسبة مئوية واضحة،
مبني على: Rubric موزون + فحوصات قاعدية حتمية + بوابات حرجة.

الاستخدام السريع:
    from evaluation import evaluate_post
    result = evaluate_post(post, brand)
    print(result["provisional_pct"])
"""
from evaluation.scorer import evaluate_post  # noqa: F401
