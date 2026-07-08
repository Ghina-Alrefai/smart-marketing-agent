"""
Shared helper for calling Gemini and parsing structured JSON responses.
Used by all agents to keep LLM interaction DRY.
"""
from __future__ import annotations

import json
import re
import time

from google import genai

from config import settings

_client = genai.Client(api_key=settings.GOOGLE_API_KEY)


def call_llm(prompt: str) -> str:
    """Call Gemini with automatic retry on 503 / high-demand errors."""
    last_exc = None
    for attempt in range(4):          # up to 4 tries: 0, 5s, 15s, 30s
        try:
            response = _client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
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


def call_llm_json(prompt: str) -> dict:
    """
    Call Gemini and parse the first JSON object found in the response.
    Returns an empty dict on failure.
    """
    raw = call_llm(prompt)
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
