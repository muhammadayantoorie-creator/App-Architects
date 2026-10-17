"""RBAC scenario baseline: clubs, players, demo users and the three RBAC leagues."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.leagues.models import League
from backend.modules.org.models import Club, Player, User
from backend.modules.org.passwords import hash_password
from backend.modules.sports.models import Sport
from backend.modules.sports.service import FULL_TIE_BREAK_ORDER

DEMO_PASSWORD = "Nascon@26"

# Seed data (names are data, never branched on in logic).
RBAC_LEAGUE_SPORT_ID = "football"
RBAC_LEAGUES = [
    {"league_id": "league-alpha-1", "tenant_id": "tenant-alpha", "name": "Alpha Premier League"},
    {"league_id": "league-alpha-2", "tenant_id": "tenant-alpha", "name": "Alpha Championship"},
    {"league_id": "league-beta-1", "tenant_id": "tenant-beta", "name": "Beta Super League"},
]

CLUBS = [
    {
        "club_id": "club-alpha-1",
        "tenant_id": "tenant-alpha",
        "name": "Alpha FC",
        "home_venue_name": "Alpha Arena",
        "latitude": 33.6844,
        "longitude": 73.0479,
        "social": {"x": "@alphafc", "instagram": "alphafc"},
        "staff": [
            {"name": "Coach Ali", "role": "coach"},
            {"name": "Sara Khan", "role": "manager"},
            {"name": "Dr. Hamza", "role": "physio"},
        ],
    },
    {
        "club_id": "club-alpha-2",
        "tenant_id": "tenant-alpha",
        "name": "Alpha Rovers",
        "home_venue_name": "Rovers Ground",
        "latitude": 31.5204,
        "longitude": 74.3587,
        "social": {"x": "@alpharovers", "instagram": "alpharovers"},
        "staff": [
            {"name": "Coach Bilal", "role": "coach"},
            {"name": "Ayesha Malik", "role": "manager"},
        ],
    },
    {
        "club_id": "club-beta-1",
        "tenant_id": "tenant-beta",
        "name": "Beta United",
        "home_venue_name": "Beta Stadium",
        "latitude": 24.8607,
        "longitude": 67.0011,
        "social": {"x": "@betaunited", "instagram": "betaunited"},
        "staff": [
            {"name": "Coach Usman", "role": "coach"},
            {"name": "Hina Raza", "role": "manager"},
        ],
    },
]

PLAYERS = [
    {
        "player_id": "player-alpha-1",
        "tenant_id": "tenant-alpha",
        "club_id": "club-alpha-1",
        "name": "Ahmed Raza",
        "position": "fw",
        "role": "captain",
    },
    {
        "player_id": "player-alpha-2",
        "tenant_id": "tenant-alpha",
        "club_id": "club-alpha-2",
        "name": "Bilal Shah",
        "position": "gk",
        "role": "starter",
    },
    {
        "player_id": "player-beta-1",
        "tenant_id": "tenant-beta",
        "club_id": "club-beta-1",
        "name": "Danish Iqbal",
        "position": "df",
        "role": "starter",
    },
]

# Order matters for the rbac-matrix response keys.
DEMO_USERS: list[dict[str, Any]] = [
    {
        "user_id": "user-admin",
        "email": "admin@nascon.test",
        "role": "super_admin",
        "tenant_id": None,
        "club_id": None,
        "player_id": None,
        "league_ids": [],
    },
    {
        "user_id": "user-organizer",
        "email": "organizer@nascon.test",
        "role": "league_organizer",
        "tenant_id": "tenant-alpha",
        "club_id": None,
        "player_id": None,
        "league_ids": ["league-alpha-1", "demo-league-ui"],
    },
    {
        "user_id": "user-manager",
        "email": "manager@nascon.test",
        "role": "club_manager",
        "tenant_id": "tenant-alpha",
        "club_id": "club-alpha-1",
        "player_id": None,
        "league_ids": [],
    },
    {
        "user_id": "user-player",
        "email": "player@nascon.test",
        "role": "player",
        "tenant_id": "tenant-alpha",
        "club_id": "club-alpha-1",
        "player_id": "player-alpha-1",
        "league_ids": [],
    },
    {
        "user_id": "user-viewer",
        "email": "viewer@nascon.test",
        "role": "viewer",
        "tenant_id": "tenant-alpha",
        "club_id": None,
        "player_id": None,
        "league_ids": [],
    },
]


def _password_salt(user_id: str) -> str:
    return f"nascon26:{user_id}"


def _default_tie_break_order(session: Session, sport_id: str) -> list[str]:
    sport = session.get(Sport, sport_id)
    if sport is not None and isinstance(sport.config, dict):
        order = sport.config.get("tie_break_order")
        if isinstance(order, list) and order:
            return list(order)
    return list(FULL_TIE_BREAK_ORDER)


def seed_org(session: Session, seed: int, _stock: dict) -> None:
    session.flush()  # tenants (10) and sports (20) must be persisted for FKs
    session.add_all(Club(**club) for club in CLUBS)
    session.flush()
    session.add_all(Player(**player) for player in PLAYERS)
    session.add_all(
        User(
            **user,
            password_hash=hash_password(DEMO_PASSWORD, _password_salt(user["user_id"])),
        )
        for user in DEMO_USERS
    )
    tie_break_order = _default_tie_break_order(session, RBAC_LEAGUE_SPORT_ID)
    session.add_all(
        League(
            league_id=league["league_id"],
            sport_id=RBAC_LEAGUE_SPORT_ID,
            tenant_id=league["tenant_id"],
            name=league["name"],
            points={"win": 3, "draw": 1, "loss": 0},
            tie_break_order=list(tie_break_order),
            qualification_spots=2,
            lots_seed=seed,
        )
        for league in RBAC_LEAGUES
    )
    session.flush()


register_reset(30, seed_org)
