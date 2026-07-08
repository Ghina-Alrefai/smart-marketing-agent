"""
Design Agent — Generates inner image then composites it with the brand template.
"""
from __future__ import annotations

from prompts.agent_prompts import DESIGN_PROMPT_GENERATOR
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
        )
    else:
        inner_url = generate_image(image_prompt, style_notes)

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
