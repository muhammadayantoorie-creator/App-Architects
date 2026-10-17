"""RBAC matrix tokens and authorization-only probe routes (SPEC 5.13).

Probes never read the request body and never mutate state. Order per request:
401 (authentication) -> 403 for roles that can never use the route -> 404 for ids
that do not exist at all -> 403 for resources outside the caller's scope -> 200.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.core.auth import current_principal, issue_token
from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.modules.leagues.models import League
from backend.modules.org import seed as _org_seed  # noqa: F401  (registers reset hook)
from backend.modules.org.models import Club, Player
from backend.modules.org.seed import DEMO_USERS

router = APIRouter()

SUPER_ADMIN = "super_admin"
ORGANIZER = "league_organizer"
CLUB_MANAGER = "club_manager"
PLAYER = "player"
VIEWER = "viewer"

ALLOWED = {"authorized": True}

RBAC_CONTEXT = {
    "tenant_id": "tenant-alpha",
    "foreign_tenant_id": "tenant-beta",
    "own_league_id": "league-alpha-1",
    "other_league_id": "league-alpha-2",
    "foreign_league_id": "league-beta-1",
    "own_club_id": "club-alpha-1",
    "other_club_id": "club-alpha-2",
    "foreign_club_id": "club-beta-1",
    "own_player_id": "player-alpha-1",
    "other_player_id": "player-alpha-2",
    "foreign_player_id": "player-beta-1",
}


def _forbidden() -> ApiError:
    return ApiError(403, "FORBIDDEN", "Not allowed")


def _is_admin(principal: dict[str, Any]) -> bool:
    return principal.get("role") == SUPER_ADMIN


def _require_roles(principal: dict[str, Any], roles: set[str]) -> None:
    if principal.get("role") not in roles:
        raise _forbidden()


def _same_tenant(principal: dict[str, Any], tenant_id: str | None) -> bool:
    return tenant_id is not None and principal.get("tenant_id") == tenant_id


def _load_club(club_id: str) -> Club:
    with SessionLocal() as session:
        club = session.get(Club, club_id)
    if club is None:
        raise ApiError(404, "NOT_FOUND", "Club not found", {"club_id": club_id})
    return club


def _load_league(league_id: str) -> League:
    with SessionLocal() as session:
        league = session.get(League, league_id)
    if league is None:
        raise ApiError(404, "LEAGUE_NOT_FOUND", "League not found", {"league_id": league_id})
    return league


def _load_player(player_id: str) -> Player:
    with SessionLocal() as session:
        player = session.get(Player, player_id)
    if player is None:
        raise ApiError(404, "PLAYER_NOT_FOUND", "Player not found", {"player_id": player_id})
    return player


@router.post("/audit/v1/rbac-matrix")
def rbac_matrix() -> dict[str, Any]:
    tokens = {user["role"]: issue_token(user) for user in DEMO_USERS}
    return {"tokens": tokens, "context": dict(RBAC_CONTEXT)}


# P1
@router.post("/audit/v1/rbac/tenants")
def probe_create_tenant(principal: dict = Depends(current_principal)) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN})
    return ALLOWED


# P2
@router.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
def probe_league_fixtures(
    league_id: str, principal: dict = Depends(current_principal)
) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN, ORGANIZER})
    league = _load_league(league_id)
    if _is_admin(principal):
        return ALLOWED
    if _same_tenant(principal, league.tenant_id) and league.league_id in principal["league_ids"]:
        return ALLOWED
    raise _forbidden()


def _club_management(club_id: str, principal: dict[str, Any]) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN, CLUB_MANAGER})
    club = _load_club(club_id)
    if _is_admin(principal):
        return ALLOWED
    if _same_tenant(principal, club.tenant_id) and principal.get("club_id") == club.club_id:
        return ALLOWED
    raise _forbidden()


# P3
@router.post("/audit/v1/rbac/clubs/{club_id}/roster")
def probe_club_roster(
    club_id: str, principal: dict = Depends(current_principal)
) -> dict[str, bool]:
    return _club_management(club_id, principal)


# P4
@router.post("/audit/v1/rbac/clubs/{club_id}/products")
def probe_club_products(
    club_id: str, principal: dict = Depends(current_principal)
) -> dict[str, bool]:
    return _club_management(club_id, principal)


# P5
@router.patch("/audit/v1/rbac/players/{player_id}")
def probe_update_player(
    player_id: str, principal: dict = Depends(current_principal)
) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN, CLUB_MANAGER, PLAYER})
    player = _load_player(player_id)
    if _is_admin(principal):
        return ALLOWED
    if not _same_tenant(principal, player.tenant_id):
        raise _forbidden()
    role = principal.get("role")
    if role == CLUB_MANAGER and player.club_id is not None and principal.get("club_id") == player.club_id:
        return ALLOWED
    if role == PLAYER and principal.get("player_id") == player.player_id:
        return ALLOWED
    raise _forbidden()


# P6
@router.get("/audit/v1/rbac/clubs/{club_id}")
def probe_read_club(
    club_id: str, principal: dict = Depends(current_principal)
) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN, ORGANIZER, CLUB_MANAGER, PLAYER, VIEWER})
    club = _load_club(club_id)
    if _is_admin(principal) or _same_tenant(principal, club.tenant_id):
        return ALLOWED
    raise _forbidden()


# P7
@router.get("/audit/v1/rbac/platform/config")
def probe_platform_config(principal: dict = Depends(current_principal)) -> dict[str, bool]:
    _require_roles(principal, {SUPER_ADMIN})
    return ALLOWED
