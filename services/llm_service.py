"""Shared Gemini helpers with observable retries and strict JSON handling."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

from config import settings
from monitoring.usage_tracker import track_llm_call

_CLIENT = None
logger = logging.getLogger("smartsocial.llm")


class LLMResponseError(RuntimeError):
    """Base error for a Gemini response that cannot safely reach an agent."""


class LLMInvalidJSONError(LLMResponseError):
    """Gemini returned text that is not one complete JSON object."""


class LLMResponseValidationError(LLMResponseError):
    """Gemini returned JSON, but it does not satisfy the agent contract."""


JSONValidator = Callable[[dict[str, Any]], dict[str, Any] | None]


def _client():
    global _CLIENT
    if _CLIENT is None:
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is required for Gemini generation")
        from google import genai

        _CLIENT = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _CLIENT


def _generation_config(temperature: float | None, *, json_mode: bool):
    from google.genai import types

    values: dict[str, Any] = {
        "max_output_tokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
    }
    if temperature is not None:
        values["temperature"] = temperature
    if json_mode:
        # Gemini's structured-output mode substantially reduces truncated
        # fences, prose around JSON, and invalid quoting.
        values["response_mime_type"] = "application/json"
    return types.GenerateContentConfig(**values)


def _parse_json_object(raw: str | None) -> dict[str, Any]:
    """Parse exactly one JSON object, tolerating only Markdown code fences."""
    text = (raw or "").strip()
    if not text:
        raise LLMInvalidJSONError("Gemini returned an empty response instead of JSON.")

    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError as exc:
        # Compatibility fallback for providers that still wrap a JSON object
        # with one short prose sentence. JSONDecoder.raw_decode avoids the
        # greedy-regex failure mode when braces appear inside quoted strings.
        start = clean.find("{")
        if start >= 0:
            try:
                payload, end = json.JSONDecoder().raw_decode(clean[start:])
                if clean[start + end :].strip():
                    raise LLMInvalidJSONError(
                        "Gemini returned extra content after the JSON object."
                    ) from exc
                if not isinstance(payload, dict):
                    raise LLMInvalidJSONError("Gemini JSON root must be an object.")
                return payload
            except (json.JSONDecodeError, LLMInvalidJSONError):
                pass
        raise LLMInvalidJSONError(
            f"Gemini returned invalid or truncated JSON at character {exc.pos}."
        ) from exc

    if not isinstance(payload, dict):
        raise LLMInvalidJSONError("Gemini JSON root must be an object.")
    return payload


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "503" in message
        or "UNAVAILABLE" in message
        or "high demand" in message.lower()
        or "429" in message
        or "rate limit" in message.lower()
        or "timeout" in message.lower()
    )


def _generate(
    prompt: str,
    *,
    temperature: float | None,
    agent_name: str | None,
    json_mode: bool,
    validator: JSONValidator | None = None,
) -> str | dict[str, Any]:
    """Call Gemini and keep provider/JSON failures inside monitoring spans."""
    max_attempts = settings.LLM_JSON_MAX_ATTEMPTS if json_mode else 4
    max_attempts = max(1, min(int(max_attempts), 4))
    retry_waits = (0, 5, 15, 30)
    last_exc: Exception | None = None
    request_prompt = prompt

    for attempt in range(max_attempts):
        try:
            # Parsing and contract validation intentionally happen before this
            # context exits. Therefore malformed JSON is stored as a failed
            # model attempt in the Consumption/Monitoring dashboard.
            with track_llm_call(
                model_name=settings.GEMINI_MODEL,
                agent_name=agent_name,
            ) as usage:
                usage.retry_count = attempt
                response = _client().models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=request_prompt,
                    config=_generation_config(temperature, json_mode=json_mode),
                )
                meta = getattr(response, "usage_metadata", None)
                usage.set_tokens(
                    input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                )
                raw = getattr(response, "text", None)
                if not json_mode:
                    if not raw:
                        raise LLMResponseError(
                            "Gemini returned an empty text response."
                        )
                    return raw

                payload = _parse_json_object(raw)
                if validator is not None:
                    validated = validator(payload)
                    if validated is not None:
                        payload = validated
                return payload

        except Exception as exc:  # track_llm_call already persisted this attempt
            last_exc = exc
            message = str(exc)
            can_retry = attempt + 1 < max_attempts

            if isinstance(exc, (LLMInvalidJSONError, LLMResponseValidationError)):
                logger.warning(
                    "llm.structured_response_rejected model=%s attempt=%s/%s "
                    "error_type=%s error=%s",
                    settings.GEMINI_MODEL,
                    attempt + 1,
                    max_attempts,
                    type(exc).__name__,
                    message[:1000],
                )
                if can_retry:
                    request_prompt = (
                        prompt
                        + "\n\nتعليمات تصحيح إلزامية: أعِد كائن JSON واحداً كاملاً فقط، "
                        "من دون Markdown أو شرح، والتزم بجميع الحقول والأعداد المطلوبة حرفياً."
                    )
                    continue
                logger.error(
                    "llm.structured_response_exhausted model=%s attempts=%s error=%s",
                    settings.GEMINI_MODEL,
                    max_attempts,
                    message[:1000],
                )
                raise

            if _is_transient_error(exc) and can_retry:
                wait = retry_waits[attempt]
                logger.warning(
                    "llm.transient_error model=%s attempt=%s/%s wait_seconds=%s "
                    "error_type=%s error=%s",
                    settings.GEMINI_MODEL,
                    attempt + 1,
                    max_attempts,
                    wait,
                    type(exc).__name__,
                    message[:1000],
                )
                if wait:
                    print(
                        f"[LLM] temporary error — waiting {wait}s before "
                        f"retry {attempt + 1}/{max_attempts - 1}..."
                    )
                    time.sleep(wait)
                continue

            logger.exception(
                "llm.call_failed model=%s prompt_chars=%s error_type=%s error=%s",
                settings.GEMINI_MODEL,
                len(prompt),
                type(exc).__name__,
                message[:1000],
            )
            raise

    if last_exc is not None:
        raise last_exc
    raise LLMResponseError("Gemini generation stopped without a response.")


def call_llm(
    prompt: str,
    temperature: float | None = None,
    agent_name: str | None = None,
) -> str:
    """Call Gemini for a plain-text response with retryable provider handling."""
    result = _generate(
        prompt,
        temperature=temperature,
        agent_name=agent_name,
        json_mode=False,
    )
    return str(result)


def call_llm_json(
    prompt: str,
    temperature: float | None = None,
    *,
    validator: JSONValidator | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Return validated JSON or raise after bounded retries.

    This function never converts a parsing/contract failure to ``{}``. The
    caller can therefore mark the campaign as failed instead of displaying a
    false successful campaign with zero posts.
    """
    result = _generate(
        prompt,
        temperature=temperature,
        agent_name=agent_name,
        json_mode=True,
        validator=validator,
    )
    if not isinstance(result, dict):  # defensive type narrowing
        raise LLMInvalidJSONError("Gemini JSON root must be an object.")
    return result
