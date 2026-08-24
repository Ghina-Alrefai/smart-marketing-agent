"""Bounded, content-based validation for user-uploaded files."""
from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile
from PIL import Image

from config import settings


_READ_CHUNK_BYTES = 1024 * 1024
_MAX_IMAGE_PIXELS = 25_000_000
_SAFE_IMAGE_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    extension: str
    width: int
    height: int


async def read_upload_limited(
    file: UploadFile,
    *,
    max_bytes: int | None = None,
) -> bytes:
    """Read at most the configured upload limit, independent of Content-Length."""
    limit = max_bytes or settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    parts: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"حجم الملف يتجاوز الحد المسموح ({settings.MAX_UPLOAD_SIZE_MB} MB).",
            )
        parts.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="الملف فارغ.")
    return b"".join(parts)


async def validate_image_upload(file: UploadFile) -> ValidatedImage:
    """Accept only genuinely decodable PNG/JPEG/WebP images.

    The server chooses the extension from the decoded format, not the supplied
    filename. This prevents HTML/SVG/script payloads from being served from the
    same-origin ``/uploads`` mount under an attacker-controlled suffix.
    """
    content = await read_upload_limited(file)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                if image_format not in _SAFE_IMAGE_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail="يُسمح فقط بصور PNG أو JPEG أو WebP.",
                    )
                if width <= 0 or height <= 0 or width * height > _MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=400,
                        detail="أبعاد الصورة غير صالحة أو كبيرة جداً.",
                    )
                image.verify()
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=400, detail="أبعاد الصورة كبيرة جداً.")
    except (OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(
            status_code=400,
            detail="الملف ليس صورة صالحة من نوع PNG أو JPEG أو WebP.",
        ) from exc

    return ValidatedImage(
        content=content,
        extension=_SAFE_IMAGE_EXTENSIONS[image_format],
        width=width,
        height=height,
    )
