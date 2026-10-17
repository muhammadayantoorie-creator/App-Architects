"""Sliding-window rate limit for /api/v1/* (100 requests per rolling 10 s per client IP).

/audit/v1/* and /health are never limited. Redis sorted sets are shared across
processes; if Redis is unavailable an in-process window is used instead.
"""

from __future__ import annotations

import math
import threading
import time
import uuid
from collections import deque

from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.core.errors import error_response
from backend.core.redis_client import get_redis

LIMITED_PREFIX = "/api/v1/"
LIMIT = 100
WINDOW_SECONDS = 10.0
KEY_PREFIX = "ratelimit:api:"
REDIS_RETRY_AFTER_FAILURE = 15.0

_local_lock = threading.Lock()
_local_windows: dict[str, deque[float]] = {}
_redis_down_until = 0.0


def client_ip(scope: Scope) -> str:
    for key, value in scope.get("headers", []):
        if key.lower() == b"x-forwarded-for":
            first = value.decode("latin-1").split(",")[0].strip()
            if first:
                return first
    client = scope.get("client")
    if client:
        return str(client[0])
    return "unknown"


def _retry_after(oldest: float, now: float) -> int:
    return max(1, math.ceil(oldest + WINDOW_SECONDS - now))


def _check_redis(ip: str, now: float) -> tuple[bool, int]:
    client = get_redis()
    key = KEY_PREFIX + ip
    pipe = client.pipeline()
    pipe.zremrangebyscore(key, "-inf", now - WINDOW_SECONDS)
    pipe.zcard(key)
    pipe.zrange(key, 0, 0, withscores=True)
    _, count, oldest = pipe.execute()
    if int(count) >= LIMIT:
        oldest_score = float(oldest[0][1]) if oldest else now
        return False, _retry_after(oldest_score, now)
    pipe = client.pipeline()
    pipe.zadd(key, {f"{now:.6f}:{uuid.uuid4().hex}": now})
    pipe.expire(key, int(WINDOW_SECONDS) + 1)
    pipe.execute()
    return True, 0


def _check_local(ip: str, now: float) -> tuple[bool, int]:
    with _local_lock:
        window = _local_windows.setdefault(ip, deque())
        while window and window[0] <= now - WINDOW_SECONDS:
            window.popleft()
        if len(window) >= LIMIT:
            return False, _retry_after(window[0], now)
        window.append(now)
        if len(_local_windows) > 10_000:  # drop idle clients
            for stale_ip in [k for k, v in _local_windows.items() if not v]:
                _local_windows.pop(stale_ip, None)
        return True, 0


def check_rate_limit(ip: str, now: float | None = None) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds). Counts the request only when allowed."""
    global _redis_down_until
    now = time.time() if now is None else now
    if time.monotonic() >= _redis_down_until:
        try:
            return _check_redis(ip, now)
        except Exception:
            _redis_down_until = time.monotonic() + REDIS_RETRY_AFTER_FAILURE
    return _check_local(ip, now)


def reset_local_state() -> None:
    """Clear the in-process fallback windows (used by tests)."""
    with _local_lock:
        _local_windows.clear()


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(LIMITED_PREFIX):
            await self.app(scope, receive, send)
            return
        allowed, retry_after = await run_in_threadpool(check_rate_limit, client_ip(scope))
        if allowed:
            await self.app(scope, receive, send)
            return
        response = error_response(
            429,
            "RATE_LIMITED",
            "Too many requests",
            {"limit": LIMIT, "window_seconds": int(WINDOW_SECONDS), "retry_after": retry_after},
        )
        response.headers["Retry-After"] = str(retry_after)
        await response(scope, receive, send)
