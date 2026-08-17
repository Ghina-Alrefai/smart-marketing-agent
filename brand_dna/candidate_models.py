from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeneratedCandidate(BaseModel):
    """Strict contract shared by generation and Brand-DNA prediction.

    The public generation field remains ``hook_type``. The feature pipeline
    converts it to the grouped SHAP feature ``hook_style`` internally.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=160)
    caption: str = Field(min_length=20, max_length=5000)
    campaign_goal: str = Field(min_length=1, max_length=200)
    campaign_type: str = Field(min_length=1, max_length=240)
    product_category: str = Field(min_length=1, max_length=200)
    brand_name: str = Field(min_length=1, max_length=200)
    day: str = Field(min_length=1, max_length=80)
    time_bucket: str = Field(min_length=1, max_length=80)
    season: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=1, max_length=120)
    dialect: str = Field(min_length=1, max_length=240)
    cta_presence: str = Field(min_length=1, max_length=120)
    cta_type: str = Field(min_length=1, max_length=200)
    tone: str = Field(min_length=1, max_length=300)
    writing_style: str = Field(min_length=1, max_length=400)
    hook_type: str = Field(min_length=1, max_length=300)
    content_pillar: str = Field(min_length=1, max_length=300)
    number_of_ctas: int = Field(ge=0, le=8)
    number_of_hashtags: int = Field(ge=0, le=30)
    number_of_products: int = Field(ge=0, le=20)
    contains_human: str = Field(min_length=1, max_length=80)
    dominant_colors: str = Field(min_length=1, max_length=500)
    logo_position: str = Field(min_length=1, max_length=500)
    text_in_image: str = Field(max_length=1000)
    visual_style: str = Field(min_length=1, max_length=300)
    layout_type: str = Field(min_length=1, max_length=300)
    # The current renderer creates one coherent asset per post. Carousel/Reel
    # requests use a cover/thumbnail, never a grid of several frames.
    image_count: int = Field(ge=1, le=1)
    is_product_post: str = Field(min_length=1, max_length=80)

    @field_validator("dominant_colors", "logo_position", "text_in_image", mode="before")
    @classmethod
    def normalize_list_like_text(cls, value: Any) -> Any:
        if isinstance(value, list):
            return "; ".join(str(item).strip() for item in value if str(item).strip())
        return value

    def prediction_input(self) -> dict[str, Any]:
        """Return the exact flat mapping expected by ``predict_candidate``."""

        return self.model_dump(mode="python")


class GeneratedDesignPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    image_prompt_en: str = Field(min_length=20, max_length=8000)
    designer_notes_ar: str = Field(min_length=20, max_length=8000)
