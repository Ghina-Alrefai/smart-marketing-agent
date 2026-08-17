from __future__ import annotations

import re
from typing import Any


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if value != value:  # NaN
            return default
    except Exception:
        pass
    return str(value).strip()


def count_emojis(text: str) -> int:
    try:
        import emoji

        return int(emoji.emoji_count(text))
    except Exception:
        # Broad fallback covering the common emoji blocks used in the dataset.
        pattern = re.compile(
            "["
            "\U0001F300-\U0001FAFF"
            "\U00002700-\U000027BF"
            "\U00002600-\U000026FF"
            "]",
            flags=re.UNICODE,
        )
        return len(pattern.findall(text))


def contains_any(value: Any, keywords: list[str]) -> int:
    text = safe_text(value).lower()
    return int(any(keyword.lower() in text for keyword in keywords))


def normalize_logo_position(value: Any) -> str:
    text = safe_text(value, "Unknown").lower()
    if not text or text == "unknown":
        return "Unknown"
    if "not clearly" in text or "missing" in text or "none" in text:
        return "missing_or_unclear"
    has_alboraq = "boraq" in text or "البراق" in text
    has_samsung = "samsung" in text or "سامسونج" in text
    has_top_left = "top-left" in text or "top left" in text
    has_top_right = "top-right" in text or "top right" in text
    if has_alboraq and has_samsung and has_top_left and has_top_right:
        return "dual_brand_top_corners"
    if "top" in text:
        return "top_area"
    if "bottom" in text:
        return "bottom_area"
    if "center" in text or "centre" in text:
        return "center_area"
    return "other"


def first_existing(mapping: dict[str, Any], names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default
