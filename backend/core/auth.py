"""JWT (HS256) issuing/verification and the current-principal dependency.

Public API used by other modules: ``issue_token(user)`` and ``current_principal(request)``.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import jwt
from fastapi import Request

from backend.core.errors import ApiError

ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 3600 * 2
CLAIM_KEYS = ("role", "tenant_id", "club_id", "player_id", "league_ids")


def _secret() -> str:
    explicit = os.environ.get("JWT_SECRET")
    if explicit:
        return explicit
    salt = os.environ.get("DAY1_SALT", "")
    return hashlib.sha256(("jwt:" + salt).encode("utf-8")).hexdigest()


def _field(user: Any, name: str) -> Any:
    if isinstance(user, dict):
        return user.get(name)
    return getattr(user, name, None)


def issue_token(user: Any, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    """Sign a token for a user ORM row or a dict with the same field names."""
    now = int(time.time())
    league_ids = _field(user, "league_ids")
    claims = {
        "sub": _field(user, "user_id"),
        "role": _field(user, "role"),
        "tenant_id": _field(user, "tenant_id"),
        "club_id": _field(user, "club_id"),
        "player_id": _field(user, "player_id"),
        "league_ids": list(league_ids) if isinstance(league_ids, (list, tuple)) else [],
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def _unauthenticated(message: str) -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message)


def decode_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthenticated("Token expired") from exc
    except Exception as exc:  # malformed, bad signature, alg:none, missing claims
        raise _unauthenticated("Invalid token") from exc
    if not isinstance(claims, dict) or not isinstance(claims.get("sub"), str):
        raise _unauthenticated("Invalid token")
    if not isinstance(claims.get("role"), str):
        raise _unauthenticated("Invalid token")
    return claims


def principal_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    league_ids = claims.get("league_ids")
    return {
        "user_id": claims["sub"],
        "sub": claims["sub"],
        "role": claims.get("role"),
        "tenant_id": claims.get("tenant_id"),
        "club_id": claims.get("club_id"),
        "player_id": claims.get("player_id"),
        "league_ids": list(league_ids) if isinstance(league_ids, list) else [],
    }


def current_principal(request: Request) -> dict[str, Any]:
    """FastAPI dependency: verified Bearer token -> principal dict, else 401 UNAUTHENTICATED."""
    header = request.headers.get("authorization")
    if not header:
        raise _unauthenticated("Missing Authorization header")
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthenticated("Authorization must be a Bearer token")
    return principal_from_claims(decode_token(token))
