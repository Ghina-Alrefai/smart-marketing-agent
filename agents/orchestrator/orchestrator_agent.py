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
from agents.orchestrator.entity_extractor import extract_entities, detect_days, parse_schedule_time
from tools.db_tools import get_products, get_product, get_brand

# ── تعريف الحقول المطلوبة لكل نية ────────────────────────────────────────────
REQUIRED = {
    "WRITE_POST": ["product_id"],
    "CREATE_DESIGN": ["product_id"],
    "WRITE_AND_DESIGN": ["product_id"],
    "REVIEW": ["review_text"],
    "GET_STRATEGY": [],
    "FULL_PIPELINE": ["days"],
    "CREATE_CAMPAIGN": ["days"],
    "GET_TRENDS": [],
    "SCHEDULE_POST": ["schedule_time"],
}
NEEDS_PRODUCT = {"WRITE_POST", "CREATE_DESIGN", "WRITE_AND_DESIGN"}
NEEDS_IMAGE = {"CREATE_DESIGN", "WRITE_AND_DESIGN"}

_SLOT_QUESTION = {
    "days": "كم يوماً تريد أن تغطّي الخطة؟ (مثلاً 7)",
    "review_text": "الصق النص الذي تريد مني مراجعته.",
    "schedule_time": "متى تريد نشر المنشور؟ (مثلاً: غداً الساعة 8، أو 2026-08-05 18:00)",
}


# ── نصوص تفاعلية ─────────────────────────────────────────────────────────────
_GREETING_MESSAGE = (
    "أهلاً وسهلاً! 👋 أنا مساعدك التسويقي الذكي لفيسبوك. أقدر أساعدك بـ:\n"
    "✍️ كتابة منشور احترافي لأي منتج\n"
    "🎨 تصميم صورة تسويقية جاهزة للنشر\n"
    "📝 كتابة منشور + تصميم معاً\n"
    "🔎 مراجعة وتقييم نص جاهز\n"
    "🧭 اقتراح أفضل منتج/استراتيجية للنشر\n"
    "📈 عرض التريندات والمواضيع الرائجة\n"
    "🚀 إنشاء حملة تسويقية كاملة\n"
    "🗓️ جدولة المنشورات في وقت محدد\n\n"
    "شو حابّة نبدأ فيه؟ 😊"
)


def _product_name(pid) -> str:
    if not pid:
        return ""
    p = get_product(pid)
    return p.get("title", "") if p else ""


def _success_message(session, intent) -> str:
    """رسالة نجاح تفاعلية ومحدّدة بحسب النية والمنتج (لا «تم ✅» فقط)."""
    name = _product_name(session.slots.get("product_id"))
    who = f"للمنتج «{name}»" if name else ""
    if intent == "WRITE_POST":
        return f"تمام! ✍️ كتبتلك منشوراً {who} كما طلبت. تحبّي أصمّم له صورة كمان؟".replace("  ", " ")
    if intent == "CREATE_DESIGN":
        return f"تفضّلي! 🎨 صمّمتلك صورة {who} كما طلبت.".replace("  ", " ")
    if intent == "WRITE_AND_DESIGN":
        return f"جاهز! 📝🎨 كتبتلك منشوراً وصمّمت صورة {who} كما طلبت.".replace("  ", " ")
    if intent == "REVIEW":
        return "خلّصت المراجعة 🔎 تحت التفاصيل والملاحظات."
    if intent == "GET_STRATEGY":
        return "جهّزتلك اقتراح الاستراتيجية 🧭 شوفي التفاصيل تحت."
    if intent == "GET_TRENDS":
        return "هي أبرز التريندات الرائجة 📈"
    if intent == "SCHEDULE_POST":
        return "تمام! 🗓️ جدولت المنشور، وبيظهر بقسم «المجدولة»."
    if intent in ("FULL_PIPELINE", "CREATE_CAMPAIGN"):
        return "انطلقت الحملة! 🚀 عم أشتغل عليها بالخلفية، تابعي التقدّم بصفحة «الحملات»."
    return "تم بنجاح ✅"


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
    elif slot == "schedule_time":
        iso = parse_schedule_time(message)
        if iso:
            session.slots["schedule_time"] = iso
            session.slots["schedule_time_text"] = message.strip()
            session.awaiting = None


# ── الدالة الرئيسية ──────────────────────────────────────────────────────────
def handle_message(user_id: int, brand_id: int, message: str,
                   session_id: str | None = None, dry_run: bool = False) -> dict:
    from monitoring.usage_tracker import trace_context, agent_context
    with trace_context(user_id=user_id), agent_context("orchestrator_agent"):
        return _handle_message(user_id, brand_id, message, session_id, dry_run)


def _handle_message(user_id: int, brand_id: int, message: str,
                    session_id: str | None, dry_run: bool) -> dict:
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
        if ents.get("schedule_time"):
            session.slots["schedule_time"] = ents["schedule_time"]
            session.slots["schedule_time_text"] = message.strip()
        if ents.get("review_text"):
            session.slots["review_text"] = ents["review_text"]
        if ents.get("product_name"):
            pid = _match_product(user_id, ents["product_name"], [])
            if pid:
                session.slots["product_id"] = pid
            else:
                session.slots["_product_name_hint"] = ents["product_name"]
        # تضمين التريند في الحملة إن ذُكر صراحةً
        if session.intent == "CREATE_CAMPAIGN":
            t = message.lower()
            if any(w in t for w in ("تريند", "ترند", "رائج", "trend")):
                session.slots["include_trends"] = True

    # التحية / طلب المساعدة — ردّ ودّي تفاعلي
    if session.intent == "GREETING":
        session.clear_task()
        return _resp(session, "info", _GREETING_MESSAGE)

    if session.intent in (None, "UNKNOWN"):
        session.clear_task()
        return _resp(session, "info",
                     "لم أفهم طلبك تماماً 🤔 بس ولا يهمّك! تقدر تطلب مثلاً:\n"
                     "• «اكتب منشور عن كذا»\n• «صمّم صورة لمنتج كذا»\n"
                     "• «راجع هذا النص»\n• «ما هي التريندات الرائجة؟»\n"
                     "• «اعمل حملة كاملة»\n• «جدول المنشور غداً»")

    # منع الجدولة بلا منشور جاهز في الجلسة
    if session.intent == "SCHEDULE_POST" and not session.cache.get("last_post"):
        session.clear_task()
        return _resp(session, "info",
                     "لا يوجد منشور جاهز لجدولته. اكتب منشوراً أولاً (مثلاً «اكتب منشور عن ...») ثم اطلب جدولته.")

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
    done_msg = _success_message(session, intent_done)
    session.clear_task()
    return _resp(session, "result", done_msg, executed=intent_done, data=result)


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


def _wad_via_idea(guidelines: dict, product_analysis: dict, pid: int,
                  skip_image: bool, dry_run: bool, brand_id: int,
                  include_design: bool = True) -> dict:
    """
    WRITE_AND_DESIGN عبر آلية الحملة الموحّدة (اقتراح E):
    فكرة قانونية واحدة (post_count=1) تُمرَّر لكاتب المحتوى والمصمّم معاً،
    فيضمن أن النص والصورة يعبّران عن *نفس* المفهوم — تماماً كالحملة الكاملة.
    """
    if dry_run:
        idea = {"concept": "(stub) فكرة موحّدة", "main_message": "(stub) رسالة",
                "visual_direction": "(stub) اتجاه بصري متّسق"}
        return {"hook": "(stub) خطّاف", "caption": "(stub) نص المنشور", "cta": "اطلب الآن",
                "hashtags": ["#تجريبي"], "idea": idea,
                "design": {"image_url": "(stub).png", "design_prompt": "(stub) prompt",
                           "visual_concept": idea["visual_direction"]},
                "review": {"approved": None, "notes": "(stub) requires human approval"},
                "intelligence": {"scoring_mode": "dry_run", "human_approval_required": True}}

    from workflows.campaign_pipeline import _build_brand_guide
    from agents.idea.idea_agent import generate_post_ideas
    from services.campaign_intelligence import generate_evaluated_post

    brand_guide = _build_brand_guide(guidelines)
    prod = get_product(pid) or {}
    product_ctx = {
        "id": pid, "name": prod.get("title", ""), "description": prod.get("description", ""),
        "price": prod.get("price"), "category": prod.get("category", ""),
        "image_url": "" if skip_image else prod.get("image_url", ""),
        "analysis": product_analysis,
    }
    # استراتيجية مصغّرة لبوست واحد (يحتاجها وكيل الأفكار كسياق)
    strategy = {"campaign_objective": "زيادة المبيعات", "main_message": "",
                "content_pillars": [], "recommended_post_count": 1}

    ideas = generate_post_ideas(strategy, [product_ctx], brand_guide, [], post_count=1)
    idea_post = (ideas.get("posts") or [{}])[0]

    evaluated = generate_evaluated_post(
        index=1,
        idea_post=idea_post,
        product=product_ctx,
        brand_guide=brand_guide,
        brand_id=brand_id,
        campaign_goals=["زيادة المبيعات"],
        start_date=None,
        dry_run=False,
        include_design=include_design,
    )
    content = evaluated["content"]
    design = evaluated["design"]
    review = evaluated["review"]

    return {
        "hook": content.get("hook", ""), "caption": content.get("caption", ""),
        "cta": content.get("cta", ""), "hashtags": content.get("hashtags", []),
        "idea": idea_post.get("idea", {}),
        # نضيف image_url (اسم يفهمه الشات) بجانب image من مخرَج design_for_idea
        "design": {**design, "image_url": design.get("image", "")},
        "review": review,
        "intelligence": evaluated["intelligence"],
    }


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

    if intent == "GET_TRENDS":
        from agents.trends.trends_agent import fetch_trends
        niche = "" if dry_run else (get_brand(brand_id) or {}).get("business_description", "")
        return fetch_trends(niche)

    if intent == "SCHEDULE_POST":
        from agents.scheduling.scheduling_agent import schedule_post
        last = session.cache.get("last_post", {})
        return schedule_post(user_id, last, slots.get("schedule_time"),
                             slots.get("schedule_time_text", ""), dry_run)

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

    # الحملة الكاملة (خطة/حملة) — كلاهما يستخدم campaign_pipeline الموحّد
    if intent in ("FULL_PIPELINE", "CREATE_CAMPAIGN"):
        return _launch_campaign(session, user_id, brand_id, slots, dry_run)

    # المسارات التي تحتاج تحليل منتج: WRITE_POST / CREATE_DESIGN / WRITE_AND_DESIGN
    if dry_run:
        product_analysis = {"_stub": True}
    else:
        from agents.product.product_analysis_agent import analyze_product
        product_analysis = analyze_product(product_id=pid, brand_guidelines=g_json)
    pa_json = json.dumps(product_analysis, ensure_ascii=False)
    out: dict = {}

    # WRITE_AND_DESIGN → عبر آلية الحملة نفسها (فكرة قانونية واحدة تضمن اتساق النص والصورة)
    if intent == "WRITE_AND_DESIGN":
        out = _wad_via_idea(guidelines, product_analysis, pid,
                            bool(slots.get("skip_image")), dry_run, brand_id,
                            include_design=True)
        session.cache["last_post"] = {
            "hook": out.get("hook", ""), "caption": out.get("caption", ""),
            "cta": out.get("cta", ""), "hashtags": out.get("hashtags", []),
            "image_url": (out.get("design") or {}).get("image_url", ""),
        }
        return out

    if intent == "WRITE_POST":
        if dry_run:
            content = {"hook": "(stub) خطّاف", "caption": "(stub) نص المنشور",
                       "cta": "اطلب الآن", "hashtags": ["#تجريبي"]}
            out.update(content)
            out["review"] = {"approved": None, "notes": "(stub) requires human approval"}
            out["intelligence"] = {"scoring_mode": "dry_run", "human_approval_required": True}
        else:
            out = _wad_via_idea(
                guidelines, product_analysis, pid, True, False, brand_id,
                include_design=False,
            )

    if intent == "CREATE_DESIGN":
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

    # نحفظ آخر منشور في الجلسة لتتمكّن نية الجدولة من استخدامه لاحقاً
    session.cache["last_post"] = {
        "hook": out.get("hook", ""), "caption": out.get("caption", ""),
        "cta": out.get("cta", ""), "hashtags": out.get("hashtags", []),
        "image_url": (out.get("design") or {}).get("image_url", "") if isinstance(out.get("design"), dict) else "",
    }
    return out


def _launch_campaign(session, user_id, brand_id, slots, dry_run) -> dict:
    """
    ينشئ خطة حملة (بالمعمارية الجديدة) ويشغّل campaign_pipeline في الخلفية.
    يجمع إعداد الحملة: المنتجات (المختار أو الكل)، الأهداف، الأيام، وتضمين التريند.
    """
    days = slots.get("days", 7)
    product_ids = [slots["product_id"]] if slots.get("product_id") else []
    include_trends = bool(slots.get("include_trends"))
    goals = slots.get("goals") or ["زيادة المبيعات"]

    if dry_run:
        return {"plan_id": 0, "days": days, "mode": "campaign", "status": "stub",
                "include_trends": include_trends, "product_ids": product_ids,
                "message": f"(تجريبي) حملة {days} أيام بالمعمارية الجديدة"}

    # إن طُلبت التريندات: استدعِ أداة التريند واجعلها سياقاً للحملة
    selected_trends = []
    if include_trends:
        from agents.trends.trends_agent import fetch_trends
        niche = (get_brand(brand_id) or {}).get("business_description", "")
        selected_trends = fetch_trends(niche).get("trends", [])

    from database.session import SessionLocal
    from database.models import ContentPlan
    with SessionLocal() as db:
        plan = ContentPlan(user_id=user_id, brand_id=brand_id, days=days,
                           campaign_goal=goals[0], campaign_goals=goals,
                           product_ids=product_ids, include_trends=include_trends,
                           selected_trends=selected_trends, mode="campaign",
                           status="pending", campaign_name="حملة من الشات")
        db.add(plan); db.commit(); db.refresh(plan)
        plan_id = plan.id

    from workflows.campaign_pipeline import run_campaign_pipeline
    threading.Thread(target=run_campaign_pipeline, args=(plan_id,), daemon=True).start()

    return {"plan_id": plan_id, "days": days, "mode": "campaign", "status": "started",
            "include_trends": include_trends, "product_ids": product_ids,
            "message": f"بدأت حملة {days} أيام بالمعمارية الجديدة. تابع الحالة عبر /plans/{plan_id}"}
