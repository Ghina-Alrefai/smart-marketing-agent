"""
Image generation via Gemini.
- generate_image: pure text-to-image
- generate_image_with_product: uses product image as reference
"""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

import httpx
from google import genai
from google.genai import types

from config import settings

_client = genai.Client(api_key=settings.GOOGLE_API_KEY)

GENERATED_DIR = Path(settings.UPLOAD_DIR) / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _save_image_bytes(image_bytes: bytes, mime: str) -> str:
    ext = mime.split("/")[-1]
    ext = ext if ext in ("png", "jpeg", "jpg", "webp") else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = GENERATED_DIR / filename
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    url = f"/uploads/generated/{filename}"
    print(f"[ImageGen] Saved: {url} ({len(image_bytes)} bytes)")
    return url


def _extract_image_from_response(response) -> str:
    for part in response.candidates[0].content.parts:
        if not part.inline_data:
            continue
        mime = part.inline_data.mime_type or ""
        if not mime.startswith("image/"):
            continue
        raw = part.inline_data.data
        image_bytes = raw if isinstance(raw, bytes) else base64.b64decode(raw)
        return _save_image_bytes(image_bytes, mime)
    print("[ImageGen] No image part in response")
    return ""


def generate_image(prompt: str, style_notes: str = "") -> str:
    """Pure text-to-image generation."""
    full_prompt = f"{prompt}. Style: {style_notes}" if style_notes else prompt
    try:
        response = _client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )
        return _extract_image_from_response(response)
    except Exception as exc:
        print(f"[ImageGen] Error: {exc}")
        return ""


def generate_image_with_product(
    prompt: str,
    style_notes: str = "",
    product_image_url: str = "",
) -> str:
    """
    Generate a marketing image using the product image as visual reference.
    Sends product image + prompt to Gemini for image editing/enhancement.
    """
    full_prompt = (
        f"Create a professional marketing social media post image. "
        f"Use the provided product image as the main subject. "
        f"{prompt}. Style: {style_notes}"
    )

    # Fetch product image bytes
    product_bytes: bytes | None = None
    product_mime = "image/jpeg"
    try:
        if product_image_url.startswith("/uploads/"):
            local_path = Path(settings.UPLOAD_DIR) / product_image_url.replace("/uploads/", "")
            if local_path.exists():
                with open(local_path, "rb") as f:
                    product_bytes = f.read()
                suffix = local_path.suffix.lower().lstrip(".")
                product_mime = f"image/{suffix}" if suffix else "image/jpeg"
        elif product_image_url.startswith("http"):
            r = httpx.get(product_image_url, timeout=10)
            product_bytes = r.content
            ct = r.headers.get("content-type", "image/jpeg")
            product_mime = ct.split(";")[0].strip()
    except Exception as exc:
        print(f"[ImageGen] Could not load product image: {exc}")

    if not product_bytes:
        # Fallback to text-only generation
        return generate_image(prompt, style_notes)

    try:
        contents = [
            types.Part.from_bytes(data=product_bytes, mime_type=product_mime),
            full_prompt,
        ]
        response = _client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )
        result = _extract_image_from_response(response)
        if result:
            return result
    except Exception as exc:
        print(f"[ImageGen] Product-image generation failed: {exc}, falling back")

    # Fallback
    return generate_image(prompt, style_notes)
