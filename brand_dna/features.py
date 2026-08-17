from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .constants import (
    BASE_NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    COLOR_FAMILIES,
    CONTENT_PILLAR_PATTERNS,
    HOOK_STYLE_PATTERNS,
    TONE_TOKENS,
    WRITING_STYLE_PATTERNS,
)
from .text_utils import contains_any, count_emojis, normalize_logo_position, safe_text

ALIASES: dict[str, list[str]] = {
    "post_id": ["post_id", "Post ID"],
    "campaign_id": ["campaign_id", "Campaign ID"],
    "caption": ["caption", "Caption"],
    "campaign_goal": ["campaign_goal", "Campaign Goal"],
    "campaign_type": ["campaign_type", "Campaign_Type"],
    "product_category": ["product_category", "Product_Category", "Product Category"],
    "brand_name": ["brand_name", "Brand_Name", "Brand Name"],
    "day": ["day", "Day"],
    "time_bucket": ["time_bucket", "Time_Bucket", "Time Bucket"],
    "season": ["season", "Season"],
    "language": ["language", "Language.1", "Language"],
    "dialect": ["dialect", "Dialect"],
    "cta_presence": ["cta_presence", "CTA_Presence"],
    "cta_type": ["cta_type", "CTA_Type"],
    "tone": ["tone", "Tone"],
    "writing_style": ["writing_style", "Writing Style"],
    "hook_type": ["hook_type", "Hook_Type"],
    "content_pillar": ["content_pillar", "Content_Pillar"],
    "number_of_ctas": ["number_of_ctas", "Number of CTAs"],
    "number_of_hashtags": ["number_of_hashtags", "Number of Hashtags"],
    "number_of_products": ["number_of_products", "Number of Products"],
    "contains_human": ["contains_human", "Contains Human"],
    "dominant_colors": ["dominant_colors", "Dominant Colors"],
    "logo_position": ["logo_position", "Logo Position"],
    "text_in_image": ["text_in_image", "Text in Image"],
    "visual_style": ["visual_style", "Visual_Style"],
    "layout_type": ["layout_type", "Layout_Type"],
    "image_count": ["image_count", "Image_Count"],
    "is_product_post": ["is_product_post", "Is_Product_Post"],
    "image_path": ["image_path", "Image Path"],
    "relative_performance_index": [
        "relative_performance_index",
        "Relative_Performance_Index",
    ],
    "weighted_engagement": ["weighted_engagement", "Weighted_Engagement"],
    "performance_class": ["performance_class", "Performance_Class"],
}

TEXT_COLUMNS = {
    "caption",
    "campaign_goal",
    "campaign_type",
    "product_category",
    "brand_name",
    "day",
    "time_bucket",
    "season",
    "language",
    "dialect",
    "cta_presence",
    "cta_type",
    "tone",
    "writing_style",
    "hook_type",
    "content_pillar",
    "contains_human",
    "dominant_colors",
    "logo_position",
    "text_in_image",
    "visual_style",
    "layout_type",
    "is_product_post",
    "image_path",
}


def _find_series(df: pd.DataFrame, aliases: list[str]) -> pd.Series:
    for alias in aliases:
        if alias in df.columns:
            return df[alias]
    return pd.Series([np.nan] * len(df), index=df.index)


def canonicalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    canonical = pd.DataFrame(index=df.index)
    for name, aliases in ALIASES.items():
        canonical[name] = _find_series(df, aliases)

    for column in TEXT_COLUMNS:
        canonical[column] = canonical[column].map(lambda value: safe_text(value, "Unknown"))

    canonical["caption"] = canonical["caption"].replace("Unknown", "")
    canonical["text_in_image"] = canonical["text_in_image"].replace("Unknown", "")
    canonical["image_path"] = canonical["image_path"].replace("Unknown", "")

    for column in [
        "number_of_ctas",
        "number_of_hashtags",
        "number_of_products",
        "image_count",
        "relative_performance_index",
        "weighted_engagement",
        "performance_class",
    ]:
        canonical[column] = pd.to_numeric(canonical[column], errors="coerce")

    # Derive caption statistics from the actual caption so training and inference agree.
    captions = canonical["caption"].fillna("").astype(str)
    canonical["caption_length"] = captions.str.len().astype(float)
    canonical["word_count"] = captions.map(lambda value: len(value.split())).astype(float)
    canonical["emoji_count"] = captions.map(count_emojis).astype(float)

    canonical["number_of_hashtags"] = canonical["number_of_hashtags"].where(
        canonical["number_of_hashtags"].notna(),
        captions.map(lambda value: len(re.findall(r"(?<!\w)#[\w\u0600-\u06FF]+", value))),
    )

    for column in ["number_of_ctas", "number_of_hashtags", "number_of_products", "image_count"]:
        canonical[column] = canonical[column].fillna(0).astype(float)

    canonical["text_in_image_length"] = canonical["text_in_image"].str.len().astype(float)
    canonical["text_in_image_word_count"] = canonical["text_in_image"].map(
        lambda value: len(value.split())
    ).astype(float)
    canonical["logo_position_category"] = canonical["logo_position"].map(
        normalize_logo_position
    )
    return canonical


def prepare_base_features(canonical: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=canonical.index)

    for column in CATEGORICAL_FEATURES:
        output[column] = canonical[column].fillna("Unknown").astype(str)

    for column in BASE_NUMERIC_FEATURES:
        output[column] = pd.to_numeric(canonical[column], errors="coerce").fillna(0).astype(float)

    for token in TONE_TOKENS:
        output[f"tone__{token}"] = canonical["tone"].map(
            lambda value, token=token: contains_any(value, [token])
        ).astype(float)

    hook_and_style = canonical["hook_type"].fillna("") + "; " + canonical[
        "writing_style"
    ].fillna("")
    for family, keywords in HOOK_STYLE_PATTERNS.items():
        output[f"hook_style__{family}"] = hook_and_style.map(
            lambda value, keywords=keywords: contains_any(value, keywords)
        ).astype(float)

    for family, keywords in WRITING_STYLE_PATTERNS.items():
        output[f"writing__{family}"] = canonical["writing_style"].map(
            lambda value, keywords=keywords: contains_any(value, keywords)
        ).astype(float)

    for family, keywords in CONTENT_PILLAR_PATTERNS.items():
        output[f"pillar__{family}"] = canonical["content_pillar"].map(
            lambda value, keywords=keywords: contains_any(value, keywords)
        ).astype(float)

    for family in COLOR_FAMILIES:
        output[f"color__{family}"] = canonical["dominant_colors"].map(
            lambda value, family=family: contains_any(value, [family])
        ).astype(float)

    return output


def group_for_source_feature(source_feature: str) -> str:
    if source_feature.startswith("tone__"):
        return "tone"
    if source_feature.startswith("hook_style__"):
        return "hook_style"
    if source_feature.startswith("writing__"):
        return "writing_style"
    if source_feature.startswith("pillar__"):
        return "content_pillar"
    if source_feature.startswith("color__"):
        return "dominant_colors"
    if source_feature == "logo_position_category":
        return "logo_position"
    if source_feature in {"text_in_image_length", "text_in_image_word_count"}:
        return "text_in_image"
    return source_feature


def feature_value_map(
    canonical_row: Mapping[str, Any],
    similarities: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    similarities = similarities or {}
    return {
        "campaign_goal": canonical_row.get("campaign_goal"),
        "campaign_type": canonical_row.get("campaign_type"),
        "product_category": canonical_row.get("product_category"),
        "brand_name": canonical_row.get("brand_name"),
        "day": canonical_row.get("day"),
        "time_bucket": canonical_row.get("time_bucket"),
        "season": canonical_row.get("season"),
        "language": canonical_row.get("language"),
        "dialect": canonical_row.get("dialect"),
        "cta_presence": canonical_row.get("cta_presence"),
        "cta_type": canonical_row.get("cta_type"),
        "tone": canonical_row.get("tone"),
        "hook_style": canonical_row.get("hook_type"),
        "writing_style": canonical_row.get("writing_style"),
        "content_pillar": canonical_row.get("content_pillar"),
        "caption_length": canonical_row.get("caption_length"),
        "word_count": canonical_row.get("word_count"),
        "emoji_count": canonical_row.get("emoji_count"),
        "number_of_ctas": canonical_row.get("number_of_ctas"),
        "number_of_hashtags": canonical_row.get("number_of_hashtags"),
        "number_of_products": canonical_row.get("number_of_products"),
        "contains_human": canonical_row.get("contains_human"),
        "dominant_colors": canonical_row.get("dominant_colors"),
        "logo_position": canonical_row.get("logo_position"),
        "visual_style": canonical_row.get("visual_style"),
        "layout_type": canonical_row.get("layout_type"),
        "image_count": canonical_row.get("image_count"),
        "is_product_post": canonical_row.get("is_product_post"),
        "text_in_image": canonical_row.get("text_in_image"),
        "text_similarity_to_success": similarities.get("text_similarity_to_success"),
        "image_similarity_to_success": similarities.get("image_similarity_to_success"),
    }


def canonicalize_candidate(candidate: Mapping[str, Any]) -> pd.DataFrame:
    return canonicalize_dataframe(pd.DataFrame([dict(candidate)]))
