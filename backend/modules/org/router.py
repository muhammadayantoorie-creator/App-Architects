"""Read-only organisation API for the app (tenant-scoped, Bearer JWT)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.core.auth import current_principal
from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.modules.org import seed as _org_seed  # noqa: F401  (registers reset hook)
from backend.modules.org.models import Club, Player

router = APIRouter()


def club_to_dict(club: Club) -> dict[str, Any]:
    return {
        "club_id": club.club_id,
        "tenant_id": club.tenant_id,
        "name": club.name,
        "home_venue_name": club.home_venue_name,
        "latitude": club.latitude,
        "longitude": club.longitude,
        "social": club.social or {},
        "staff": club.staff or [],
    }


def player_to_dict(player: Player) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "tenant_id": player.tenant_id,
        "club_id": player.club_id,
        "name": player.name,
        "position": player.position,
        "role": player.role,
    }


def _visible(principal: dict[str, Any], tenant_id: str | None) -> bool:
    return principal.get("role") == "super_admin" or (
        tenant_id is not None and principal.get("tenant_id") == tenant_id
    )


@router.get("/api/v1/clubs")
def list_clubs(principal: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        query = select(Club).order_by(Club.club_id)
        if principal.get("role") != "super_admin":
            query = query.where(Club.tenant_id == principal.get("tenant_id"))
        clubs = session.scalars(query).all()
    return {"clubs": [club_to_dict(club) for club in clubs]}


@router.get("/api/v1/clubs/{club_id}")
def get_club(club_id: str, principal: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        club = session.get(Club, club_id)
        if club is None:
            raise ApiError(404, "NOT_FOUND", "Club not found", {"club_id": club_id})
        if not _visible(principal, club.tenant_id):
            raise ApiError(403, "FORBIDDEN", "Not allowed")
        players = session.scalars(
            select(Player).where(Player.club_id == club_id).order_by(Player.player_id)
        ).all()
        result = club_to_dict(club)
        result["players"] = [player_to_dict(player) for player in players]
    return result
