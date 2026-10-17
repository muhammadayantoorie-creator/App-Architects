"""League configuration validation and fixture stream registration."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.state import get_value
from backend.modules.leagues.models import League, LeagueTeam, MatchStream
from backend.modules.sports.models import Sport

DEFAULT_POINTS = {"win": 3, "draw": 1, "loss": 0}
TIE_BREAKS = {
    "h2h_points",
    "h2h_diff",
    "overall_diff",
    "scored",
    "fair_play",
    "draw_lots",
}
_MISSING = object()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _schema(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "League body must be an object",
            {"fields": ["body"]},
        )

    fields: set[str] = set()
    league_id = body.get("league_id")
    sport_id = body.get("sport_id")
    teams = body.get("teams")
    fixtures = body.get("fixtures")
    if not is_valid_id(league_id):
        fields.add("league_id")
    if not is_valid_id(sport_id):
        fields.add("sport_id")

    teams_valid = isinstance(teams, list)
    if not teams_valid or not 2 <= len(teams) <= 40:
        fields.add("teams")
    valid_teams: list[str] = []
    if teams_valid:
        for index, team_id in enumerate(teams):
            if not is_valid_id(team_id):
                fields.add(f"teams.{index}")
            elif team_id in valid_teams:
                fields.add("teams")
            else:
                valid_teams.append(team_id)

    fixtures_valid = isinstance(fixtures, list)
    if not fixtures_valid:
        fields.add("fixtures")
    valid_fixtures: list[dict[str, str]] = []
    if fixtures_valid:
        for index, fixture in enumerate(fixtures):
            prefix = f"fixtures.{index}"
            if not isinstance(fixture, dict):
                fields.add(prefix)
                continue
            match_id = fixture.get("match_id")
            home = fixture.get("home")
            away = fixture.get("away")
            row_valid = True
            if not is_valid_id(match_id):
                fields.add(f"{prefix}.match_id")
                row_valid = False
            if not is_valid_id(home):
                fields.add(f"{prefix}.home")
                row_valid = False
            if not is_valid_id(away):
                fields.add(f"{prefix}.away")
                row_valid = False
            if is_valid_id(home) and is_valid_id(away) and home == away:
                fields.add(f"{prefix}.away")
                row_valid = False
            if teams_valid and is_valid_id(home) and home not in valid_teams:
                fields.add(f"{prefix}.home")
                row_valid = False
            if teams_valid and is_valid_id(away) and away not in valid_teams:
                fields.add(f"{prefix}.away")
                row_valid = False
            if row_valid:
                valid_fixtures.append(
                    {"match_id": match_id, "home": home, "away": away}
                )

    points_in = body.get("points", {})
    points = DEFAULT_POINTS.copy()
    if not isinstance(points_in, dict):
        fields.add("points")
    else:
        for key in DEFAULT_POINTS:
            if key in points_in:
                if not _is_int(points_in[key]):
                    fields.add(f"points.{key}")
                else:
                    points[key] = points_in[key]

    qualification = body.get("qualification")
    spots = qualification.get("spots") if isinstance(qualification, dict) else None
    if not isinstance(qualification, dict):
        fields.add("qualification")
    elif not _is_int(spots):
        fields.add("qualification.spots")
    elif teams_valid and not 1 <= spots <= len(valid_teams):
        fields.add("qualification.spots")

    lots_seed = body.get("lots_seed", _MISSING)
    if lots_seed is not _MISSING and not _is_int(lots_seed):
        fields.add("lots_seed")

    tie_order = body.get("tie_break_order", _MISSING)
    tie_order_out: list[str] | None = None
    if tie_order is not _MISSING:
        if not isinstance(tie_order, list):
            fields.add("tie_break_order")
        else:
            seen: set[str] = set()
            tie_order_out = []
            for index, criterion in enumerate(tie_order):
                if (
                    not isinstance(criterion, str)
                    or criterion not in TIE_BREAKS
                    or criterion in seen
                ):
                    fields.add(f"tie_break_order.{index}")
                    continue
                seen.add(criterion)
                if criterion != "draw_lots":
                    tie_order_out.append(criterion)
            tie_order_out.append("draw_lots")

    if fields:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "League configuration is invalid",
            {"fields": sorted(fields)},
        )

    return {
        "league_id": league_id,
        "sport_id": sport_id,
        "teams": valid_teams,
        "fixtures": valid_fixtures,
        "points": points,
        "tie_break_order": tie_order_out,
        "qualification_spots": spots,
        "lots_seed": None if lots_seed is _MISSING else lots_seed,
    }


def create_league(session: Session, body: Any, *, tenant_id: str | None = None) -> dict[str, Any]:
    config = _schema(body)

    sport = session.get(Sport, config["sport_id"])
    if sport is None:
        raise ApiError(
            404,
            "SPORT_NOT_FOUND",
            f"Sport {config['sport_id']} was not found.",
            {"sport_id": config["sport_id"]},
        )

    league_id = config["league_id"]
    if session.get(League, league_id) is not None:
        raise ApiError(
            409,
            "LEAGUE_EXISTS",
            f"League {league_id} already exists.",
            {"league_id": league_id},
        )

    match_ids = [fixture["match_id"] for fixture in config["fixtures"]]
    if len(set(match_ids)) != len(match_ids):
        raise ApiError(
            409,
            "MATCH_EXISTS",
            "A fixture match id is repeated.",
            {"match_id": next(item for item in match_ids if match_ids.count(item) > 1)},
        )
    if match_ids:
        existing_id = session.scalar(
            select(MatchStream.match_id)
            .where(MatchStream.match_id.in_(match_ids))
            .limit(1)
        )
        if existing_id is not None:
            raise ApiError(
                409,
                "MATCH_EXISTS",
                f"Match {existing_id} already exists.",
                {"match_id": existing_id},
            )

    points = config["points"]
    sport_order = sport.config.get("tie_break_order", list(TIE_BREAKS))
    tie_break_order = config["tie_break_order"] or [
        item for item in sport_order if item != "draw_lots"
    ] + ["draw_lots"]
    lots_seed = config["lots_seed"]
    if lots_seed is None:
        lots_seed = int(get_value(session, "last_reset_seed", "42"))

    league = League(
        league_id=league_id,
        sport_id=sport.sport_id,
        tenant_id=tenant_id,
        points=points,
        tie_break_order=tie_break_order,
        qualification_spots=config["qualification_spots"],
        lots_seed=lots_seed,
    )
    session.add(league)
    session.add_all(
        LeagueTeam(league_id=league_id, team_id=team_id)
        for team_id in config["teams"]
    )
    session.add_all(
        MatchStream(
            match_id=fixture["match_id"],
            sport_id=sport.sport_id,
            league_id=league_id,
            home_team_id=fixture["home"],
            away_team_id=fixture["away"],
            status="upcoming",
            version=0,
            draw_allowed=bool(sport.config["draw_allowed"]),
        )
        for fixture in config["fixtures"]
    )
    session.flush()
    return {
        "league_id": league_id,
        "status": "created",
        "team_count": len(config["teams"]),
        "fixture_count": len(config["fixtures"]),
    }
