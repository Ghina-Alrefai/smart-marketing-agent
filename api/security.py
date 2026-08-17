"""
أدوات الأمان: تجزئة كلمة المرور (للأدمِن الثابت) + إصدار/تحقّق رمز الجلسة.

- كلمة المرور: PBKDF2-HMAC-SHA256 من المكتبة القياسية (بلا اعتماد خارجي).
- رمز الجلسة: JWT عبر PyJWT إن توفّر، وإلا رمز HMAC بسيط موقّع بالمكتبة القياسية.
- التحقق من Google ID token: google-auth إن توفّر، وإلا تحقق عبر tokeninfo كحلّ بديل.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

import httpx

from config import settings

# ── كلمة المرور (PBKDF2) ─────────────────────────────────────────────────────
_PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ── رمز الجلسة ───────────────────────────────────────────────────────────────
try:
    import jwt  # PyJWT

    _HAS_JWT = True
except ImportError:  # pragma: no cover
    _HAS_JWT = False


def _signing_key() -> str:
    """يضمن مفتاحاً بطول ≥32 بايت (متطلّب HS256) باشتقاقه من SECRET_KEY إن كان قصيراً."""
    key = settings.SECRET_KEY or "change-me-in-production"
    if len(key.encode()) >= 32:
        return key
    return hashlib.sha256(key.encode()).hexdigest()  # 64 hex char = 64 بايت


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_session_token(user_id: int, role: str) -> str:
    exp = int(time.time()) + settings.SESSION_TOKEN_DAYS * 86400
    payload = {"sub": str(user_id), "role": role, "exp": exp}
    if _HAS_JWT:
        return jwt.encode(payload, _signing_key(), algorithm="HS256")
    # بديل: HMAC موقّع يدوياً
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_session_token(token: str) -> dict | None:
    if _HAS_JWT:
        try:
            return jwt.decode(token, _signing_key(), algorithms=["HS256"])
        except Exception:
            return None
    # بديل HMAC
    try:
        body, sig = token.split(".")
        expected = _b64url(
            hmac.new(_signing_key().encode(), body.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


# ── التحقق من Google ID token ────────────────────────────────────────────────
try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    _HAS_GOOGLE_AUTH = True
except ImportError:  # pragma: no cover
    _HAS_GOOGLE_AUTH = False


class GoogleTokenError(Exception):
    pass


def verify_google_id_token(token: str) -> dict:
    """يتحقق من صحّة الـ ID token ويُعيد بيانات المستخدم (sub, email, name, picture)."""
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise GoogleTokenError("GOOGLE_CLIENT_ID غير مضبوط في الإعدادات")

    if _HAS_GOOGLE_AUTH:
        try:
            info = google_id_token.verify_oauth2_token(
                token, google_requests.Request(), client_id
            )
        except Exception as e:  # noqa: BLE001
            raise GoogleTokenError(f"رمز Google غير صالح: {e}") from e
    else:
        # بديل: نقطة tokeninfo من Google (تتحقق من التوقيع والانتهاء)
        try:
            resp = httpx.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": token},
                timeout=10,
            )
            resp.raise_for_status()
            info = resp.json()
        except Exception as e:  # noqa: BLE001
            raise GoogleTokenError(f"تعذّر التحقق من رمز Google: {e}") from e
        if info.get("aud") != client_id:
            raise GoogleTokenError("جمهور الرمز (aud) لا يطابق GOOGLE_CLIENT_ID")

    if info.get("email_verified") in (False, "false"):
        raise GoogleTokenError("بريد Google غير موثّق")

    return {
        "sub": info.get("sub"),
        "email": (info.get("email") or "").lower(),
        "name": info.get("name") or (info.get("email") or "").split("@")[0],
        "picture": info.get("picture"),
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
