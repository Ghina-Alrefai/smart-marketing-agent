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
_MAX_PRODUCTS_PER_UPLOAD = 5_000


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
    """يستخرج أول رقم من نص مثل «520 USD» أو «1,050 USD» أو «١٢٠$».

    الفاصلة التي تفصل ثلاث خانات («1,050») تُعامل كفاصل آلاف، أما الفاصلة
    التي يليها عدد مختلف من الخانات («12,5») فتُعامل كفاصلة عشرية.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace("٫", ".").replace("٬", ",")
    m = re.search(r"\d[\d,.  ]*\d|\d", text)
    if not m:
        return None
    num = re.sub(r"[  ]", "", m.group())
    # فاصل آلاف: فاصلة يتبعها ثلاث خانات ثم نهاية/فاصل آخر
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", num):
        num = num.replace(",", "")
    else:
        num = num.replace(",", ".")
    # نُبقي أول فاصلة عشرية فقط
    if num.count(".") > 1:
        head, _, tail = num.partition(".")
        num = head + "." + tail.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


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
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        wb.close()
        return [], ["الملف فارغ"]

    col = _build_column_index(header)
    if "title" not in col:
        wb.close()
        return [], ["لم يُعثر على عمود «اسم المنتج». تأكّد من رؤوس الأعمدة."]

    def cell(row, field):
        i = col.get(field)
        return row[i] if (i is not None and i < len(row)) else None

    products: list[dict] = []
    for n, row in enumerate(rows, start=2):
        if len(products) >= _MAX_PRODUCTS_PER_UPLOAD:
            errors.append(
                f"تم إيقاف الاستيراد عند {_MAX_PRODUCTS_PER_UPLOAD} منتج لحماية الخادم."
            )
            break
        title = str(cell(row, "title") or "").strip()
        if not title:
            continue   # نتخطّى الأسطر الفارغة بصمت
        images = _parse_images(cell(row, "images"))
        products.append({
            "title": title[:300],
            "description": (str(cell(row, "description") or "").strip()[:10_000] or None),
            "price": _parse_price(cell(row, "price")),
            "category": _parse_category(cell(row, "category")),
            "image_url": images[0] if images else None,   # الصورة الأساسية
            "image_urls": images,
            "source_url": (str(cell(row, "source_url") or "").strip()[:500] or None),
        })

    wb.close()

    if not products:
        errors.append("لم يُعثر على أي منتج صالح في الملف.")
    return products, errors
