"""
Design Agent — Generates inner image then composites it with the brand template.
"""
from __future__ import annotations

import json

from prompts.agent_prompts import DESIGN_PROMPT_GENERATOR
from prompts.campaign_prompts import DESIGN_FROM_IDEA_PROMPT
from services.llm_service import call_llm_json
from tools.image_generation import generate_image_with_product, generate_image
from tools.template_overlay import apply_brand_template


def create_design(
    brand_name: str,
    brand_colors: str,
    visual_style: str,
    design_mood: str,
    template_url: str,       
    product_info: str,
    product_image_url: str,
    post_type: str,
) -> dict:
    has_product_image = bool(product_image_url and product_image_url.strip())

    # Step 1: LLM builds image prompt for the inner content only
    prompt = DESIGN_PROMPT_GENERATOR.format(
        brand_name=brand_name,
        brand_colors=brand_colors,
        visual_style=visual_style,
        design_mood=design_mood,
        product_info=product_info,
        has_product_image="true" if has_product_image else "false",
        post_type=post_type,
        external_template_mode=(
            "مفعّل: القالب سيضاف برمجياً بعد التوليد؛ ممنوع وضع أي شعار أو قالب داخل الصورة."
            if template_url and template_url.strip()
            else "غير مفعّل."
        ),
    )

    design_data = call_llm_json(prompt)
    image_prompt = design_data.get("image_prompt", "")
    style_notes  = design_data.get("style_notes", "")

    if not image_prompt:
        design_data["image_url"] = ""
        return design_data

    # Step 2: Generate inner image
    if has_product_image:
        inner_url = generate_image_with_product(
            prompt=image_prompt,
            style_notes=style_notes,
            product_image_url=product_image_url,
            template_applied_externally=bool(template_url and template_url.strip()),
        )
    else:
        inner_url = generate_image(
            image_prompt,
            style_notes,
            template_applied_externally=bool(template_url and template_url.strip()),
        )

    if not inner_url:
        design_data["image_url"] = ""
        return design_data

    # Step 3: Composite with brand template
    final_url = apply_brand_template(
        inner_image_path=inner_url,
        template_url=template_url,
    )

    design_data["image_url"] = final_url
    return design_data


# ── Campaign architecture (data-driven, idea-centric) ───────────────────────
def design_for_idea(
    idea_post: dict,
    content: dict,
    product: dict,
    brand_guide: dict,
    photo_style: str = "الأنسب للمنتج",
    avoid_concepts: list[str] | None = None,
) -> dict:
    """
    Design Agent لمعمارية الحملة: يبني التمثيل البصري *لنفس* فكرة البوست
    (لا يخترع مفهوماً مختلفاً عن النص)، ثم يولّد الصورة ويركّبها على قالب البراند.

    photo_style    : أسلوب التصوير المطلوب لهذا البوست (تدوير عبر الحملة لتنوّع بصري).
    avoid_concepts : ملخّصات بصرية لبوستات سابقة بنفس الحملة، تُمرَّر كسياق سلبي (تجنّب التكرار).

    يعيد: {post_id, design_prompt, visual_concept, layout, text_elements,
           brand_elements, image}
    """
    post_id = idea_post.get("post_id", "")
    product_image_url = product.get("image_url", "") or ""
    has_product_image = bool(product_image_url.strip())
    avoid = avoid_concepts or []
    avoid_text = "\n".join(f"- {c}" for c in avoid) if avoid else "لا يوجد (هذا أول بوست)."

    # 1) LLM يبني وصف التصميم المهيكل من الفكرة + النص (للاتّساق)
    prompt = DESIGN_FROM_IDEA_PROMPT.format(
        idea=json.dumps(idea_post.get("idea", {}), ensure_ascii=False),
        content=json.dumps(content, ensure_ascii=False),
        product=json.dumps(product, ensure_ascii=False),
        brand_name=brand_guide.get("brand_name", ""),
        brand_colors=", ".join(brand_guide.get("brand_colors", [])),
        visual_style=brand_guide.get("visual_style", "modern"),
        has_product_image="true" if has_product_image else "false",
        photo_style=photo_style,
        avoid_concepts=avoid_text,
        external_template_mode=(
            "مفعّل: القالب المرفوع سيضاف بعد التوليد، لذلك ممنوع تضمين شعار أو إطار أو قالب أو نص داخل الصورة."
            if brand_guide.get("template_url")
            else "غير مفعّل."
        ),
    )
    # حرارة عالية: التصميم مهمّة إبداعية
    design_data = call_llm_json(prompt, temperature=0.9)

    image_prompt = design_data.get("design_prompt", "")
    style_notes = design_data.get("visual_concept", "")
    image_url = ""

    # 2) توليد الصورة (بنفس مفهوم الفكرة) وتركيبها على قالب البراند
    if image_prompt:
        if has_product_image:
            inner = generate_image_with_product(
                image_prompt,
                style_notes,
                product_image_url,
                template_applied_externally=bool(brand_guide.get("template_url")),
            )
        else:
            inner = generate_image(
                image_prompt,
                style_notes,
                template_applied_externally=bool(brand_guide.get("template_url")),
            )
        if inner:
            image_url = apply_brand_template(
                inner_image_path=inner,
                template_url=brand_guide.get("template_url", ""),
            )

    return {
        "post_id": post_id,
        "design_prompt": image_prompt,
        "visual_concept": design_data.get("visual_concept", ""),
        "layout": design_data.get("layout", ""),
        "text_elements": design_data.get("text_elements", []),
        "brand_elements": design_data.get("brand_elements", []),
        "image": image_url,
    }
