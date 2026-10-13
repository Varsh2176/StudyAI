"""
M11 — Simple in-process sliding-window rate limiter.

No external dependencies. Suitable for single-worker deployments.
Multi-worker hosts need a shared store (out of scope); document that limitation.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int, message: str = "Too many requests. Try again later."):
        super().__init__(message)
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.message = message


class SlidingWindowRateLimiter:
    """Thread-safe fixed sliding window keyed by an opaque client string."""

    def __init__(self, *, max_attempts: int, window_seconds: int):
        self.max_attempts = max(1, int(max_attempts))
        self.window_seconds = max(1, int(window_seconds))
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def check(self, key: str) -> None:
        """Raise RateLimitExceeded if the key has exceeded the window budget."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_attempts:
                retry_after = int(self.window_seconds - (now - bucket[0])) + 1
                raise RateLimitExceeded(retry_after_seconds=retry_after)
            bucket.append(now)


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def get_auth_rate_limiter() -> SlidingWindowRateLimiter:
    """
    Shared limiter for login/register.

    Defaults: 10 attempts / 60 seconds per client key.
    Override with AUTH_RATE_LIMIT_ATTEMPTS and AUTH_RATE_LIMIT_WINDOW_SECONDS.
    """
    global _AUTH_LIMITER
    if _AUTH_LIMITER is None:
        _AUTH_LIMITER = SlidingWindowRateLimiter(
            max_attempts=_env_int("AUTH_RATE_LIMIT_ATTEMPTS", 10, minimum=3, maximum=100),
            window_seconds=_env_int("AUTH_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=10, maximum=3600),
        )
    return _AUTH_LIMITER


_AUTH_LIMITER: Optional[SlidingWindowRateLimiter] = None


def reset_auth_rate_limiter_for_tests() -> None:
    """Test helper — clears buckets and rebuilds from current env."""
    global _AUTH_LIMITER
    _AUTH_LIMITER = None
    get_auth_rate_limiter().reset()


def client_rate_key(request_client_host: Optional[str], email: Optional[str] = None) -> str:
    host = (request_client_host or "unknown").strip() or "unknown"
    identity = (email or "").strip().lower()
    if identity:
        return f"{host}|{identity}"
    return host


def rate_limit_headers(exc: RateLimitExceeded) -> Dict[str, str]:
    return {"Retry-After": str(exc.retry_after_seconds)}


def describe_auth_rate_limit() -> Tuple[int, int]:
    limiter = get_auth_rate_limiter()
    return limiter.max_attempts, limiter.window_seconds
