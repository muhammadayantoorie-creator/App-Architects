"""Shared Redis client. REDIS_URL=fakeredis:// selects an in-process fake (tests only)."""

from __future__ import annotations

import os
import threading

import redis

_lock = threading.Lock()
_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                if url.startswith("fakeredis"):
                    import fakeredis

                    _client = fakeredis.FakeRedis(decode_responses=True)
                else:
                    _client = redis.Redis.from_url(
                        url, socket_timeout=2, socket_connect_timeout=2, decode_responses=True
                    )
    return _client
