"""
M14 — General academic AI Tutor service.

Provider-independent interface with a Gemini REST implementation.
This module is intentionally separate from RAG/notes grounding (M15–M16).
It never fabricates uploaded-note citations.

M11/tutor hardening: configurable timeouts and bounded retries for transient
provider failures (timeouts / 5xx). Does not retry auth or quota errors.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


# gemini-2.5-flash returns HTTP 404 for new API keys; use a current generateContent model.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Gemini can exceed 20s under load; keep client timeouts above this value.
DEFAULT_TIMEOUT_SECONDS = 40
MAX_TIMEOUT_SECONDS = 90
DEFAULT_MAX_RETRIES = 1  # total attempts = 1 + retries
MAX_HISTORY_MESSAGES = 20
_RETRYABLE_HTTP_STATUS = frozenset({500, 502, 503, 504})
DISCLAIMER = (
    "StudyWise AI Tutor provides educational explanations for learning support. "
    "Verify critical facts with your course materials and instructors. "
    "This response is not grounded in uploaded study notes."
)


class TutorError(Exception):
    """Base tutor service error."""


class TutorNotConfiguredError(TutorError):
    """Raised when no AI provider credentials are configured."""


class TutorTimeoutError(TutorError):
    """Raised when the provider request times out."""


class TutorProviderError(TutorError):
    """Raised for provider HTTP/API failures (including rate limits)."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def get_tutor_api_key() -> Optional[str]:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return key or None


def get_tutor_model() -> str:
    return (os.getenv("TUTOR_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_tutor_timeout_seconds() -> int:
    raw = os.getenv("TUTOR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        value = int(raw)
        return max(5, min(value, MAX_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def get_tutor_max_retries() -> int:
    """Number of retries after the first attempt (0–2). Not used for 429/401/403/404."""
    raw = os.getenv("TUTOR_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
    try:
        value = int(raw)
        return max(0, min(value, 2))
    except (TypeError, ValueError):
        return DEFAULT_MAX_RETRIES


def is_tutor_configured() -> bool:
    return get_tutor_api_key() is not None


def get_tutor_status() -> Dict[str, Any]:
    configured = is_tutor_configured()
    return {
        "configured": configured,
        "provider": "gemini" if configured else None,
        "model": get_tutor_model() if configured else None,
        "timeout_seconds": get_tutor_timeout_seconds(),
        "max_retries": get_tutor_max_retries(),
        "message": (
            "AI Tutor is ready."
            if configured
            else (
                "AI Tutor is not configured. Set GEMINI_API_KEY in backend/.env "
                "and restart the API server."
            )
        ),
    }


def _build_system_instruction(
    subject: Optional[str],
    profile_context: Optional[Dict[str, Any]],
) -> str:
    parts = [
        "You are StudyWise AI Tutor, a helpful academic study assistant for college students.",
        "Explain concepts clearly in student-friendly language with short examples when useful.",
        "Be accurate and humble: if you are unsure, say so and suggest how the student can verify.",
        "Do not invent citations, page numbers, uploaded notes, or claim answers came from student documents.",
        "Do not request or repeat passwords or API keys.",
        "Keep answers focused and educational.",
    ]
    if subject and subject.strip():
        parts.append(f"The student is currently studying the subject/topic: {subject.strip()}.")
    if profile_context:
        course = profile_context.get("course")
        branch = profile_context.get("branch")
        year = profile_context.get("year")
        subjects = profile_context.get("subjects")
        context_bits = []
        if course:
            context_bits.append(f"course={course}")
        if branch:
            context_bits.append(f"branch={branch}")
        if year is not None:
            context_bits.append(f"year={year}")
        if subjects:
            if isinstance(subjects, list):
                context_bits.append("subjects=" + ", ".join(str(s) for s in subjects[:12]))
            else:
                context_bits.append(f"subjects={subjects}")
        if context_bits:
            parts.append(
                "Optional academic profile context (use only when relevant): "
                + "; ".join(context_bits)
            )
    return "\n".join(parts)


def _normalize_history(conversation_history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    if not conversation_history:
        return []

    normalized: List[Dict[str, str]] = []
    for item in conversation_history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content[:4000]})
    return normalized


def _call_gemini(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    question: str,
    conversation_history: List[Dict[str, str]],
    timeout_seconds: int,
) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    contents: List[Dict[str, Any]] = []
    for turn in conversation_history:
        gemini_role = "user" if turn["role"] == "user" else "model"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": turn["content"]}],
        })
    contents.append({
        "role": "user",
        "parts": [{"text": question}],
    })

    req_body = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024,
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(req_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        status = getattr(http_err, "code", 500)
        # Do not include response body in raised messages (may contain sensitive details).
        if status == 429:
            raise TutorProviderError(
                "The AI provider rate limit was reached. Please wait a moment and try again."
            ) from http_err
        if status in (401, 403):
            raise TutorProviderError(
                "The AI provider rejected the API key. Check GEMINI_API_KEY in backend/.env."
            ) from http_err
        if status == 404:
            raise TutorProviderError(
                "The configured AI model was not found. Check TUTOR_MODEL in backend/.env."
            ) from http_err
        if status in _RETRYABLE_HTTP_STATUS:
            raise TutorProviderError(
                f"The AI provider is temporarily unavailable (HTTP {status}). Please try again.",
                retryable=True,
            ) from http_err
        raise TutorProviderError(
            f"The AI provider returned an error (HTTP {status}). Please try again later."
        ) from http_err
    except TimeoutError as timeout_err:
        raise TutorTimeoutError(
            "The AI provider timed out. Please try again with a shorter question."
        ) from timeout_err
    except urllib.error.URLError as url_err:
        reason = getattr(url_err, "reason", None)
        if isinstance(reason, TimeoutError) or "timed out" in str(url_err).lower():
            raise TutorTimeoutError(
                "The AI provider timed out. Please try again with a shorter question."
            ) from url_err
        raise TutorProviderError(
            "Could not reach the AI provider. Check your internet connection and try again.",
            retryable=True,
        ) from url_err

    candidates = payload.get("candidates") or []
    if not candidates:
        raise TutorProviderError("The AI provider returned an empty response.", retryable=True)

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise TutorProviderError("The AI provider returned an empty answer.", retryable=True)
    return text


def _is_retryable_tutor_error(exc: BaseException) -> bool:
    if isinstance(exc, TutorTimeoutError):
        return True
    if isinstance(exc, TutorProviderError):
        return bool(getattr(exc, "retryable", False))
    return False


def answer_academic_question(
    question: str,
    *,
    subject: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    profile_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a general academic tutor answer.

    Raises TutorNotConfiguredError when credentials are missing.
    Never claims the answer came from uploaded notes.
    Retries once by default on timeouts and transient provider errors only.
    """
    cleaned = (question or "").strip()
    if not cleaned:
        raise ValueError("Question cannot be empty.")
    if len(cleaned) > 2000:
        raise ValueError("Question exceeds the maximum length of 2000 characters.")

    api_key = get_tutor_api_key()
    if not api_key:
        raise TutorNotConfiguredError(
            "AI Tutor is not configured. Set GEMINI_API_KEY in backend/.env and restart the server."
        )

    model = get_tutor_model()
    timeout_seconds = get_tutor_timeout_seconds()
    max_retries = get_tutor_max_retries()
    history = _normalize_history(conversation_history)
    system_instruction = _build_system_instruction(subject, profile_context)

    attempts = 1 + max_retries
    last_error: Optional[BaseException] = None
    for attempt in range(attempts):
        try:
            answer = _call_gemini(
                api_key=api_key,
                model=model,
                system_instruction=system_instruction,
                question=cleaned,
                conversation_history=history,
                timeout_seconds=timeout_seconds,
            )
            return {
                "answer": answer,
                "provider": "gemini",
                "model_used": model,
                "configured": True,
                "profile_context_used": bool(profile_context),
                "disclaimer": DISCLAIMER,
            }
        except (TutorTimeoutError, TutorProviderError) as exc:
            last_error = exc
            if attempt >= attempts - 1 or not _is_retryable_tutor_error(exc):
                raise
            # Brief backoff before a single retry; never log secrets or response bodies.
            time.sleep(0.75 * (attempt + 1))

    assert last_error is not None
    raise last_error
