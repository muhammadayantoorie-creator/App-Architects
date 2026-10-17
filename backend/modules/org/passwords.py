"""PBKDF2-SHA256 password hashing (standard library only)."""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

ITERATIONS = 60_000


@lru_cache(maxsize=64)
def hash_password(password: str, salt: str, iterations: int = ITERATIONS) -> str:
    """Deterministic for a fixed salt, so every reset recreates identical rows."""
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations_s, salt, digest = stored.split("$", 3)
        iterations = int(iterations_s)
    except (ValueError, AttributeError):
        return False
    if scheme != "pbkdf2_sha256" or iterations < 1:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return hmac.compare_digest(candidate, digest)
