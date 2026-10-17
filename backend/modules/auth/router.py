"""Login, current user and ping endpoints under /api/v1 (rate limited)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy import func, select

from backend.core.auth import current_principal, issue_token
from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.modules.org import seed as _org_seed  # noqa: F401  (registers reset hook)
from backend.modules.org.models import User
from backend.modules.org.passwords import verify_password
from backend.modules.tenants.models import Tenant

router = APIRouter()

LOGIN_EXPIRES_IN = 3600


def user_to_dict(user: User) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "club_id": user.club_id,
        "player_id": user.player_id,
        "league_ids": list(user.league_ids or []),
    }


def tenant_to_dict(tenant: Tenant | None) -> dict[str, Any] | None:
    if tenant is None:
        return None
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "logo_url": getattr(tenant, "logo_url", None),
        "primary_color": getattr(tenant, "primary_color", None),
        "secondary_color": getattr(tenant, "secondary_color", None),
    }


def _parse_login(body: Any) -> tuple[str, str]:
    if not isinstance(body, dict):
        raise ApiError(400, "VALIDATION_ERROR", "Body must be an object", {"fields": ["body"]})
    fields = []
    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or not email.strip() or len(email) > 254:
        fields.append("email")
    if not isinstance(password, str) or not password or len(password) > 256:
        fields.append("password")
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "Invalid login request", {"fields": fields})
    return email.strip().lower(), password


@router.post("/api/v1/auth/login")
def login(body: Any = Body(default=None)) -> dict[str, Any]:
    email, password = _parse_login(body)
    with SessionLocal() as session:
        user = session.scalars(select(User).where(func.lower(User.email) == email)).first()
    if user is None or not verify_password(password, user.password_hash):
        raise ApiError(401, "UNAUTHENTICATED", "Invalid email or password")
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "expires_in": LOGIN_EXPIRES_IN,
        "user": user_to_dict(user),
    }


@router.get("/api/v1/me")
def me(principal: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        user = session.get(User, principal["user_id"])
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "User no longer exists")
        tenant = session.get(Tenant, user.tenant_id) if user.tenant_id else None
        data = user_to_dict(user)
        tenant_data = tenant_to_dict(tenant)
    return {
        "user_id": data["user_id"],
        "email": data["email"],
        "role": data["role"],
        "tenant": tenant_data,
        "club_id": data["club_id"],
        "player_id": data["player_id"],
        "league_ids": data["league_ids"],
    }


@router.get("/api/v1/ping")
def ping() -> dict[str, bool]:
    return {"pong": True}
