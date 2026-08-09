"""
مُستورِد المنتجات من ملف Excel (.xlsx).

يقرأ ملفاً بأعمدة عربية (اسم المنتج، الوصف، السعر، الفئة، الصور، الرابط)
ويحوّله إلى قائمة منتجات جاهزة للإدراج. يدعم صوراً متعددة لكل منتج (روابط
مفصولة بـ «|» أو أسطر/فواصل).
"""
from __future__ import annotations

import io
import re

import openpyxl

# مرادفات رؤوس الأعمدة (عربي/إنجليزي) → الحقل الداخلي
_HEADER_MAP = {
    "title":       ["اسم المنتج", "الاسم", "المنتج", "name", "title", "product"],
    "description": ["الوصف", "التفاصيل", "description", "desc"],
    "price":       ["السعر", "price", "cost"],
    "category":    ["الفئة", "التصنيف", "category", "cat"],
    "images":      ["الصور", "الصورة", "images", "image", "img", "photos"],
    "source_url":  ["الرابط", "رابط المنتج", "link", "url", "source"],
}

_IMG_SPLIT = re.compile(r"[|\n،,]+")   # فواصل الصور المحتملة


def _norm(s) -> str:
    return str(s or "").strip().lower()


def _build_column_index(header_row: tuple) -> dict[str, int]:
    """يربط اسم الحقل الداخلي برقم العمود بناءً على رأس الجدول."""
    idx: dict[str, int] = {}
    for col_i, cell in enumerate(header_row):
        h = _norm(cell)
        if not h:
            continue
        for field, aliases in _HEADER_MAP.items():
            if field in idx:
                continue
            if any(_norm(a) == h or _norm(a) in h for a in aliases):
                idx[field] = col_i
                break
    return idx


def _parse_price(raw) -> float | None:
    """يستخرج أول رقم من نص مثل «520 USD» أو «١٢٠$»."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"\d+(?:[.,]\d+)?", str(raw).replace("٫", "."))
    return float(m.group().replace(",", ".")) if m else None


def _parse_category(raw) -> str | None:
    """يأخذ آخر جزء واضح من مسار الفئة «أ / ب / ج» ويقصّه إلى ≤100 حرفاً."""
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).split("/") if p.strip()]
    cat = parts[-1] if parts else str(raw).strip()
    return cat[:100]


def _parse_images(raw) -> list[str]:
    """يفكّك روابط الصور المتعددة إلى قائمة نظيفة."""
    if not raw:
        return []
    urls = [u.strip() for u in _IMG_SPLIT.split(str(raw)) if u.strip()]
    # نُبقي فقط ما يبدو رابطاً
    return [u for u in urls if u.lower().startswith(("http://", "https://", "/uploads/"))]


def parse_products_xlsx(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """
    يحلّل محتوى ملف xlsx ويعيد (منتجات، أخطاء).
    كل منتج: {title, description, price, category, image_url, image_urls, source_url}
    """
    errors: list[str] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        return [], [f"تعذّر فتح الملف: {exc}"]

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], ["الملف فارغ"]

    col = _build_column_index(rows[0])
    if "title" not in col:
        return [], ["لم يُعثر على عمود «اسم المنتج». تأكّد من رؤوس الأعمدة."]

    def cell(row, field):
        i = col.get(field)
        return row[i] if (i is not None and i < len(row)) else None

    products: list[dict] = []
    for n, row in enumerate(rows[1:], start=2):
        title = str(cell(row, "title") or "").strip()
        if not title:
            continue   # نتخطّى الأسطر الفارغة بصمت
        images = _parse_images(cell(row, "images"))
        products.append({
            "title": title[:300],
            "description": str(cell(row, "description") or "").strip() or None,
            "price": _parse_price(cell(row, "price")),
            "category": _parse_category(cell(row, "category")),
            "image_url": images[0] if images else None,   # الصورة الأساسية
            "image_urls": images,
            "source_url": (str(cell(row, "source_url") or "").strip() or None),
        })

    if not products:
        errors.append("لم يُعثر على أي منتج صالح في الملف.")
    return products, errors
