"""
Template Overlay Engine.

The user uploads a brand template (PNG with transparency).
The template contains: logo, contact bar, borders — everything fixed.
The transparent area is where the AI-generated image goes.

Flow:
  1. Load user template (RGBA)
  2. Resize AI inner image to match template size
  3. Place inner image as background layer
  4. Paste template on top — transparency preserved
  5. Save final JPEG
"""
from __future__ import annotations

import uuid
from pathlib import Path
from PIL import Image

from config import settings

GENERATED_DIR = Path(settings.UPLOAD_DIR) / "generated"
TEMPLATES_DIR = Path(settings.UPLOAD_DIR) / "templates"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def apply_brand_template(inner_image_path: str, template_url: str) -> str:
    """
    Composite AI image (background) with brand template (foreground overlay).
    Returns URL of final image. Falls back to inner image if no template.
    """
    if not template_url or not template_url.strip():
        return inner_image_path

    inner_local    = _to_local(inner_image_path)
    template_local = _to_local(template_url)

    if not inner_local or not inner_local.exists():
        print(f"[Overlay] inner image missing: {inner_image_path}")
        return inner_image_path

    if not template_local or not template_local.exists():
        print(f"[Overlay] template missing: {template_url}")
        return inner_image_path

    try:
        template = Image.open(template_local).convert("RGBA")
        tw, th   = template.size

        inner = Image.open(inner_local).convert("RGBA")
        inner = _fill_crop(inner, tw, th)

        # inner as background, template composited on top
        canvas = Image.new("RGBA", (tw, th))
        canvas.paste(inner, (0, 0))
        canvas.alpha_composite(template)

        filename = f"{uuid.uuid4().hex}_final.jpg"
        canvas.convert("RGB").save(GENERATED_DIR / filename, "JPEG", quality=93)

        url = f"/uploads/generated/{filename}"
        print(f"[Overlay] done: {url}")
        return url

    except Exception as exc:
        print(f"[Overlay] error: {exc}")
        return inner_image_path


def _to_local(url: str) -> Path | None:
    if url and url.startswith("/uploads/"):
        return Path(settings.UPLOAD_DIR) / url.replace("/uploads/", "", 1)
    return None


def _fill_crop(img: Image.Image, tw: int, th: int) -> Image.Image:
    sr = img.width / img.height
    tr = tw / th
    if sr > tr:
        nw, nh = int(img.width * th / img.height), th
    else:
        nw, nh = tw, int(img.height * tw / img.width)
    img = img.resize((nw, nh), Image.LANCZOS)
    l = (nw - tw) // 2
    t = (nh - th) // 2
    return img.crop((l, t, l + tw, t + th))
