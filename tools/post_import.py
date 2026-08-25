"""مُستورِد المنشورات المرجعية من ملف Excel وربطها بالمنتجات.

يقرأ ورقة «المنشورات» ويربط كل صف بمنتج عبر «رقم المنتج» (ترتيب المنتج
1..N بنفس ترتيب ملف استيراد المنتجات)، ثم يخزّنه في جدول product_posts.
"""
from __future__ import annotations

import io
import re

import openpyxl

_HEADER_MAP = {
    "product_ref":  ["رقم المنتج", "المنتج", "رقم", "product", "ref", "#"],
    "post_type":    ["نوع البوست", "النوع", "post_type", "type"],
    "post_goal":    ["هدف البوست", "الهدف", "post_goal", "goal"],
    "hook":         ["الهوك", "hook", "العنوان"],
    "caption":      ["الكابشن", "النص", "caption", "body"],
    "cta":          ["cta", "الدعوة", "دعوة لاتخاذ إجراء"],
    "hashtags":     ["الهاشتاغات", "الهاشتاقات", "hashtags", "tags"],
    "image_prompt": ["وصف الصورة", "برومبت", "image_prompt", "prompt"],
    "image_url":    ["رابط الصورة", "الصورة", "image_url", "image"],
    "notes":        ["ملاحظات", "notes", "note"],
}

_TAG_SPLIT = re.compile(r"[|\n،,\s]+")
_MAX_POSTS_PER_UPLOAD = 5_000


def _norm(s) -> str:
    return str(s or "").strip().lower()


def _build_column_index(header_row: tuple) -> dict[str, int]:
    idx: dict[str, int] = {}
    for col_i, cell in enumerate(header_row):
        h = _norm(cell)
        if not h:
            continue
        for field, aliases in _HEADER_MAP.items():
            if field in idx:
                continue
            if any(_norm(a) == h for a in aliases):
                idx[field] = col_i
                break
    # مطابقة جزئية لما لم يُطابَق تماماً
    for col_i, cell in enumerate(header_row):
        h = _norm(cell)
        if not h or col_i in idx.values():
            continue
        for field, aliases in _HEADER_MAP.items():
            if field in idx:
                continue
            if any(_norm(a) in h for a in aliases):
                idx[field] = col_i
                break
    return idx


def _parse_hashtags(raw) -> list[str]:
    if not raw:
        return []
    tags = [t.strip() for t in _TAG_SPLIT.split(str(raw)) if t.strip()]
    out, seen = [], set()
    for t in tags:
        t = t if t.startswith("#") else "#" + t.lstrip("#")
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t[:100])
    return out


def _parse_ref(raw) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    m = re.search(r"\d+", str(raw))
    return int(m.group()) if m else None


def parse_posts_xlsx(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """يحلّل ملف المنشورات ويعيد (منشورات، أخطاء).

    كل منشور: {product_ref, post_type, post_goal, hook, caption, cta,
    hashtags, image_prompt, image_url, notes, row}
    """
    errors: list[str] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        return [], [f"تعذّر فتح الملف: {exc}"]

    ws = wb["المنشورات"] if "المنشورات" in wb.sheetnames else wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        wb.close()
        return [], ["الملف فارغ"]

    col = _build_column_index(header)
    missing = [f for f in ("product_ref", "caption") if f not in col]
    if missing:
        wb.close()
        names = {"product_ref": "«رقم المنتج»", "caption": "«الكابشن»"}
        return [], ["لم يُعثر على عمود " + " و".join(names[m] for m in missing)]

    def cell(row, field):
        i = col.get(field)
        return row[i] if (i is not None and i < len(row)) else None

    posts: list[dict] = []
    for n, row in enumerate(rows, start=2):
        if len(posts) >= _MAX_POSTS_PER_UPLOAD:
            errors.append(
                f"تم إيقاف الاستيراد عند {_MAX_POSTS_PER_UPLOAD} منشوراً لحماية الخادم."
            )
            break
        if not any(str(c or "").strip() for c in row):
            continue   # سطر فارغ
        ref = _parse_ref(cell(row, "product_ref"))
        caption = str(cell(row, "caption") or "").strip()
        if ref is None:
            errors.append(f"سطر {n}: «رقم المنتج» مفقود أو غير رقمي — تم تخطّيه.")
            continue
        if not caption:
            errors.append(f"سطر {n}: «الكابشن» فارغ — تم تخطّيه.")
            continue
        posts.append({
            "row": n,
            "product_ref": ref,
            "post_type": (str(cell(row, "post_type") or "").strip()[:100] or None),
            "post_goal": (str(cell(row, "post_goal") or "").strip()[:200] or None),
            "hook": (str(cell(row, "hook") or "").strip()[:2_000] or None),
            "caption": caption[:10_000],
            "cta": (str(cell(row, "cta") or "").strip()[:2_000] or None),
            "hashtags": _parse_hashtags(cell(row, "hashtags")),
            "image_prompt": (str(cell(row, "image_prompt") or "").strip()[:4_000] or None),
            "image_url": (str(cell(row, "image_url") or "").strip()[:500] or None),
            "notes": (str(cell(row, "notes") or "").strip()[:2_000] or None),
        })

    wb.close()
    if not posts:
        errors.append("لم يُعثر على أي منشور صالح في الملف.")
    return posts, errors
