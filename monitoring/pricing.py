"""
أسعار نماذج الذكاء الاصطناعي — جدول قابل للتحديث بشكل مستقل عن الكود.

راجع 5.16.4: يجب أن تكون أسعار النماذج محفوظة ضمن إعدادات النظام،
بدلًا من تضمينها بشكل ثابت داخل منطق الحساب، لتسهيل تحديثها عند
تغيّر أسعار مزود الخدمة. الأسعار بالدولار لكل مليون Token.
"""

MODEL_PRICING = {
    "gemini-2.5-flash":       {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro":         {"input": 1.25,  "output": 5.00},
    "gemini-3.1-flash-image": {"input": 0.10,  "output": 0.40},
}

DEFAULT_PRICING = {"input": 0.50, "output": 1.50}


def get_model_pricing(model_name: str) -> dict:
    return MODEL_PRICING.get(model_name, DEFAULT_PRICING)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model_name: str,
) -> float:
    """Estimated Cost = (Input Tokens × Input Price) + (Output Tokens × Output Price)"""
    price = get_model_pricing(model_name)
    input_cost = (input_tokens / 1_000_000) * price["input"]
    output_cost = (output_tokens / 1_000_000) * price["output"]
    return round(input_cost + output_cost, 6)
