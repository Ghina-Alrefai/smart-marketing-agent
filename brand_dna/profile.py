from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd

from .constants import (
    COLOR_FAMILIES,
    CONTENT_PILLAR_PATTERNS,
    HOOK_STYLE_PATTERNS,
    TONE_TOKENS,
    WRITING_STYLE_PATTERNS,
)
from .features import canonicalize_dataframe
from .text_utils import contains_any


def _top(series: pd.Series, n: int = 5) -> list[str]:
    return [str(value) for value in series.replace("Unknown", pd.NA).dropna().value_counts().head(n).index]


def _top_flags(series: pd.Series, patterns: dict[str, list[str]], n: int = 5) -> list[str]:
    counts = Counter()
    for value in series.fillna(""):
        for family, keywords in patterns.items():
            if contains_any(value, keywords):
                counts[family] += 1
    return [family for family, _ in counts.most_common(n)]


def build_stable_brand_profile(df: pd.DataFrame) -> dict:
    canonical = canonicalize_dataframe(df)
    tone_counts = Counter()
    for value in canonical["tone"]:
        for token in TONE_TOKENS:
            if contains_any(value, [token]):
                tone_counts[token] += 1

    color_counts = Counter()
    for value in canonical["dominant_colors"]:
        for family in COLOR_FAMILIES:
            if contains_any(value, [family]):
                color_counts[family] += 1

    profile = {
        "schema_version": "2.0",
        "profile_type": "stable_brand_identity",
        "page_id": "al_boraq",
        "page_name": _top(df.get("Page Name", pd.Series(dtype=str)), 1)[0]
        if "Page Name" in df.columns and not df["Page Name"].dropna().empty
        else "Al Boraq Telecom",
        "language": _top(canonical["language"], 3),
        "dialects": _top(canonical["dialect"], 3),
        "caption_profile": {
            "median_word_count": float(canonical["word_count"].median()),
            "median_caption_length": float(canonical["caption_length"].median()),
            "median_emoji_count": float(canonical["emoji_count"].median()),
            "common_tones": [name for name, _ in tone_counts.most_common(5)],
            "common_hook_families": _top_flags(
                canonical["hook_type"] + "; " + canonical["writing_style"],
                HOOK_STYLE_PATTERNS,
            ),
            "common_writing_style_families": _top_flags(
                canonical["writing_style"], WRITING_STYLE_PATTERNS
            ),
            "common_cta_types": _top(canonical["cta_type"], 5),
        },
        "visual_profile": {
            "common_visual_styles": _top(canonical["visual_style"], 5),
            "common_layouts": _top(canonical["layout_type"], 5),
            "common_logo_positions": _top(canonical["logo_position"], 3),
            "common_color_families": [name for name, _ in color_counts.most_common(8)],
            "human_presence_rate": float(
                (canonical["contains_human"].str.lower() == "yes").mean()
            ),
        },
        "separation_rule": (
            "This profile contains stable identity statistics only. "
            "Performance-derived evidence and policies belong to Adaptive Memory."
        ),
    }
    canonical_json = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    profile["brand_profile_version"] = "sha256:" + hashlib.sha256(canonical_json).hexdigest()[:16]
    return profile


def save_stable_brand_profile(df: pd.DataFrame, output_path: str | Path) -> dict:
    profile = build_stable_brand_profile(df)
    Path(output_path).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile
