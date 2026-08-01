"""
Orchestrator Agent (L1) — العقل المدبّر لطبقة الـ Chat.

يفهم النية، يملأ الحقول الناقصة عبر الحوار مع المستخدم، ثم يوجّه للوكيل/المسار
المناسب من الوكلاء الموجودين (بلا أي تعديل عليهم أو على الـ Pipeline).

الدالة العامة: handle_message(user_id, brand_id, message, session_id, dry_run)
تُعيد dict فيه "type": clarification | result | info | error.
"""
from __future__ import annotations

import json
import re
import threading

from agents.orchestrator import session_store as store
from agents.orchestrator.intent_classifier import classify_intent
from agents.orchestrator.entity_extractor import extract_entities, detect_days
from tools.db_tools import get_products, get_product, get_brand

# ── تعريف الحقول المطلوبة لكل نية ────────────────────────────────────────────
REQUIRED = {
    "WRITE_POST": ["product_id"],
    "CREATE_DESIGN": ["product_id"],
    "WRITE_AND_DESIGN": ["product_id"],
    "REVIEW": ["review_text"],
    "GET_STRATEGY": [],
    "FULL_PIPELINE": ["days"],
}
NEEDS_PRODUCT = {"WRITE_POST", "CREATE_DESIGN", "WRITE_AND_DESIGN"}
NEEDS_IMAGE = {"CREATE_DESIGN", "WRITE_AND_DESIGN"}

_SLOT_QUESTION = {
    "days": "كم يوماً تريد أن تغطّي الخطة؟ (مثلاً 7)",
    "review_text": "الصق النص الذي تريد مني مراجعته.",
}


# ── ردود موحّدة ──────────────────────────────────────────────────────────────
def _resp(session, rtype, message, **extra):
    session.history.append(("agent", message))
    return {"type": rtype, "session_id": session.id, "intent": session.intent,
            "message": message, **extra}


# ── حلّ المنتج من الاسم/الرقم/القائمة ────────────────────────────────────────
def _match_product(user_id: int, text: str, options: list) -> int | None:
    text = text.strip()
    # صيغة الزر: "product_id:5"
    m = re.search(r"product_id\s*[:=]\s*(\d+)", text)
    if m:
        return int(m.group(1))
    # رقم خيار من القائمة المعروضة (1-based)
    if text.isdigit() and options:
        idx = int(text) - 1
        if 0 <= idx < len(options):
            return options[idx]["value"]["product_id"]
    # مطابقة بالاسم (تطابق جزئي غير حسّاس لحالة الأحرف)
    products = get_products(user_id)
    hits = [p for p in products if text and text.lower() in (p["title"] or "").lower()]
    if len(hits) == 1:
        return hits[0]["id"]
    return None


def _product_options(user_id: int, only_with_image: bool = False) -> list:
    opts = []
    for p in get_products(user_id):
        if only_with_image and not p.get("image_url"):
            continue
        opts.append({"label": f'{p["title"]}' + ("" if p.get("image_url") else " (بلا صورة)"),
                     "value": {"product_id": p["id"]},
                     "has_image": bool(p.get("image_url"))})
    return opts


def _ask_product(session, user_id):
    opts = _product_options(user_id)
    session.awaiting = "product_id"
    session.options = opts
    if opts:
        msg = "أي منتج تقصد؟ اختر من منتجاتك أو ارفع منتجاً جديداً من صفحة المنتجات:"
    else:
        msg = "لا أجد منتجات في حسابك. أضِف منتجاً أولاً من صفحة المنتجات ثم أخبرني."
    return _resp(session, "clarification", msg, awaiting="product_id",
                 options=opts, allow_upload=True)


def _ask_image(session, user_id):
    """المنتج بلا صورة — نعرض بدائل: منتج له صورة، أو المتابعة بلا صورة، أو رفع صورة."""
    opts = _product_options(user_id, only_with_image=True)
    session.awaiting = "product_image"
    session.options = opts
    msg = ("المنتج المختار بلا صورة، والتصميم يحتاج صورة للمنتج. تستطيع:\n"
           "• اختيار منتج آخر له صورة من القائمة،\n"
           "• أو رفع صورة لهذا المنتج من صفحة المنتجات ثم كتابة «تم الرفع»،\n"
           "• أو كتابة «بدون صورة» للمتابعة بتصميم عام بلا صورة منتج.")
    return _resp(session, "clarification", msg, awaiting="product_image",
                 options=opts, allow_upload=True)


def _ask_slot(session, slot):
    session.awaiting = slot
    return _resp(session, "clarification", _SLOT_QUESTION.get(slot, f"أحتاج معلومة: {slot}"),
                 awaiting=slot)


# ── تطبيق إجابة المستخدم على الحقل المنتظَر ──────────────────────────────────
def _apply_answer(session, user_id, message):
    slot = session.awaiting
    if slot == "product_id":
        pid = _match_product(user_id, message, session.options)
        if pid:
            session.slots["product_id"] = pid
            session.awaiting = None
    elif slot == "product_image":
        t = message.strip().lower()
        if "بدون" in t or "بلا صورة" in t:
            session.slots["skip_image"] = True
            session.awaiting = None
        elif "تم" in t or "رفعت" in t or "رفع" in t:
            session.awaiting = None  # سنعيد فحص الصورة تلقائياً
        else:
            pid = _match_product(user_id, message, session.options)
            if pid:
                session.slots["product_id"] = pid
                session.awaiting = None
    elif slot == "days":
        d = detect_days(message) or (int(re.search(r"\d+", message).group()) if re.search(r"\d+", message) else None)
        if d:
            session.slots["days"] = d
            session.awaiting = None
    elif slot == "review_text":
        session.slots["review_text"] = message.strip()
        session.awaiting = None


# ── الدالة الرئيسية ──────────────────────────────────────────────────────────
def handle_message(user_id: int, brand_id: int, message: str,
                   session_id: str | None = None, dry_run: bool = False) -> dict:
    session = store.get_or_create(session_id)
    session.history.append(("user", message))
    use_llm = not dry_run

    # (1) إن كنا ننتظر إجابة حقل، طبّقها أولاً
    if session.awaiting:
        _apply_answer(session, user_id, message)
        if session.awaiting:  # لم نفهم الإجابة → أعد السؤال
            return _ask_slot(session, session.awaiting) if session.awaiting in _SLOT_QUESTION \
                else _ask_product(session, user_id) if session.awaiting == "product_id" \
                else _ask_image(session, user_id)

    # (2) إن لا نية بعد، صنّف واستخرج الكيانات
    if not session.intent:
        intent, _ = classify_intent(message, use_llm=use_llm)
        session.intent = intent
        ents = extract_entities(message, use_llm=use_llm)
        if ents.get("days"):
            session.slots["days"] = ents["days"]
        if ents.get("post_type"):
            session.slots["post_type"] = ents["post_type"]
        if ents.get("review_text"):
            session.slots["review_text"] = ents["review_text"]
        if ents.get("product_name"):
            pid = _match_product(user_id, ents["product_name"], [])
            if pid:
                session.slots["product_id"] = pid
            else:
                session.slots["_product_name_hint"] = ents["product_name"]

    if session.intent in (None, "UNKNOWN"):
        session.clear_task()
        return _resp(session, "info",
                     "لم أفهم طلبك تماماً 🤔 تقدر تطلب مثلاً: «اكتب منشور إنستغرام عن كذا»، "
                     "«صمّم صورة لمنتج كذا»، «راجع هذا النص»، أو «اعمل خطة 7 أيام».")

    # (3) حلّ المنتج إن كانت النية تحتاجه
    if session.intent in NEEDS_PRODUCT and not session.slots.get("product_id"):
        return _ask_product(session, user_id)

    # (5) فحص الصورة للتصميم
    if session.intent in NEEDS_IMAGE and session.slots.get("product_id") \
            and not session.slots.get("skip_image"):
        prod = get_product(session.slots["product_id"])
        if not prod.get("image_url"):
            return _ask_image(session, user_id)

    # (6) فحص باقي الحقول المطلوبة
    for slot in REQUIRED.get(session.intent, []):
        if not session.slots.get(slot):
            return _ask_slot(session, slot)

    # (7) كل المعلومات جاهزة → نفّذ
    try:
        result = _execute(session, user_id, brand_id, dry_run)
    except Exception as exc:  # noqa: BLE001
        session.clear_task()
        return _resp(session, "error", f"حدث خطأ أثناء التنفيذ: {exc}")

    intent_done = session.intent
    session.clear_task()
    return _resp(session, "result", "تم ✅", executed=intent_done, data=result)


# ── التنفيذ: استدعاء الوكلاء الموجودين (بلا تعديل) ───────────────────────────
def _brand_guidelines(session, brand_id, dry_run):
    if "brand_guidelines" in session.cache:
        return session.cache["brand_guidelines"]
    if dry_run:
        g = {"_brand": get_brand(brand_id) or {}, "_stub": True}
    else:
        from agents.brand.brand_agent import analyze_brand
        g = analyze_brand(brand_id)
    session.cache["brand_guidelines"] = g
    return g


def _execute(session, user_id, brand_id, dry_run) -> dict:
    intent = session.intent
    slots = session.slots
    pid = slots.get("product_id")

    if intent == "REVIEW":
        if dry_run:
            return {"approved": True, "notes": "(stub) مراجعة تجريبية", "scores": {}}
        from agents.review.review_agent import review_post
        return review_post(brand_guidelines="{}", hook="", caption=slots["review_text"],
                           cta="", hashtags="[]", image_prompt="")

    guidelines = _brand_guidelines(session, brand_id, dry_run)
    g_json = json.dumps(guidelines, ensure_ascii=False)
    brand_info = guidelines.get("_brand", {})

    if intent == "GET_STRATEGY":
        if dry_run:
            return {"_stub": True, "recommendation": "منتج مقترح (تجريبي)"}
        from agents.strategy.strategy_agent import build_content_strategy
        return build_content_strategy(brand_guidelines=g_json, user_id=user_id,
                                      days=slots.get("days", 3),
                                      campaign_goal="زيادة المبيعات")

    if intent == "FULL_PIPELINE":
        return _launch_pipeline(user_id, brand_id, slots.get("days", 7), dry_run)

    # المسارات التي تحتاج تحليل منتج: WRITE_POST / CREATE_DESIGN / WRITE_AND_DESIGN
    if dry_run:
        product_analysis = {"_stub": True}
    else:
        from agents.product.product_analysis_agent import analyze_product
        product_analysis = analyze_product(product_id=pid, brand_guidelines=g_json)
    pa_json = json.dumps(product_analysis, ensure_ascii=False)
    out: dict = {}

    if intent in ("WRITE_POST", "WRITE_AND_DESIGN"):
        if dry_run:
            content = {"hook": "(stub) خطّاف", "caption": "(stub) نص المنشور",
                       "cta": "اطلب الآن", "hashtags": ["#تجريبي"]}
        else:
            from agents.content.content_agent import write_post_content
            content = write_post_content(
                brand_guidelines=g_json, product_analysis=pa_json,
                post_type=slots.get("post_type", "promotional"), goal="", content_angle="",
                must_use_words=", ".join(brand_info.get("must_use_words", [])),
                forbidden_words=", ".join(brand_info.get("forbidden_words", [])),
                preferred_cta=brand_info.get("preferred_cta", ""))
        out.update(content)

        if dry_run:
            out["review"] = {"approved": True, "notes": "(stub)"}
        else:
            from agents.review.review_agent import review_post
            out["review"] = review_post(
                brand_guidelines=g_json, hook=out.get("hook", ""), caption=out.get("caption", ""),
                cta=out.get("cta", ""), hashtags=json.dumps(out.get("hashtags", []), ensure_ascii=False),
                image_prompt="")

    if intent in ("CREATE_DESIGN", "WRITE_AND_DESIGN"):
        product = get_product(pid) if pid else {}
        if dry_run:
            out["design"] = {"image_url": "(stub).png", "image_prompt": "(stub) prompt"}
        else:
            from agents.design.design_agent import create_design
            out["design"] = create_design(
                brand_name=brand_info.get("brand_name", ""),
                brand_colors=", ".join(brand_info.get("brand_colors", [])),
                visual_style=brand_info.get("visual_style", "modern"),
                design_mood=product_analysis.get("suggested_design_mood", "modern clean"),
                template_url=brand_info.get("template_url", ""),
                product_info=pa_json,
                product_image_url="" if slots.get("skip_image") else product.get("image_url", ""),
                post_type=slots.get("post_type", "promotional"))

    return out


def _launch_pipeline(user_id, brand_id, days, dry_run) -> dict:
    """ينشئ خطة ويشغّل الـ Pipeline الموجود في الخلفية — بلا تعديل عليه."""
    if dry_run:
        return {"plan_id": 0, "days": days,
                "status": "stub", "message": f"(تجريبي) خطة {days} أيام"}
    from database.session import SessionLocal
    from database.models import ContentPlan
    with SessionLocal() as db:
        plan = ContentPlan(user_id=user_id, brand_id=brand_id, days=days,
                           campaign_goal="زيادة المبيعات",
                           status="pending", campaign_name="حملة من الشات")
        db.add(plan); db.commit(); db.refresh(plan)
        plan_id = plan.id

    from workflows.generate_content_plan import run_content_generation_pipeline
    threading.Thread(target=run_content_generation_pipeline, args=(plan_id,), daemon=True).start()

    return {"plan_id": plan_id, "days": days,
            "status": "started",
            "message": f"بدأ توليد خطة {days} أيام. تابع الحالة عبر /plans/{plan_id}"}
