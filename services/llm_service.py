"""
Shared helper for calling Gemini and parsing structured JSON responses.
Used by all agents to keep LLM interaction DRY.
"""
from __future__ import annotations

import json
import re
import time

from google import genai
from google.genai import types

from config import settings

_client = genai.Client(api_key=settings.GOOGLE_API_KEY)


def call_llm(prompt: str, temperature: float | None = None) -> str:
    """
    Call Gemini with automatic retry on 503 / high-demand errors.

      temperature : يتحكّم بمدى التنوّع/الإبداع في المخرَج.
                    منخفض (0.2–0.4) لمهام تحليلية دقيقة (استراتيجية/مراجعة)،
                    عالٍ (0.8–1.0) لمهام إبداعية (أفكار/كتابة/تصميم).
                    None → الإعداد الافتراضي للنموذج.
    """
    config = (types.GenerateContentConfig(temperature=temperature)
              if temperature is not None else None)
    last_exc = None
    for attempt in range(4):          # up to 4 tries: 0, 5s, 15s, 30s
        try:
            response = _client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg.lower():
                wait = [0, 5, 15, 30][attempt]
                if wait:
                    print(f"[LLM] 503 — waiting {wait}s before retry {attempt + 1}/3...")
                    time.sleep(wait)
                continue
            raise   # non-503 errors raise immediately
    raise last_exc


def call_llm_json(prompt: str, temperature: float | None = None) -> dict:
    """
    Call Gemini and parse the first JSON object found in the response.
    Returns an empty dict on failure. مرّر temperature للتحكّم بالإبداع.
    """
    raw = call_llm(prompt, temperature=temperature)
    try:
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try extracting the first {...} block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}
