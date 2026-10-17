"""Fixture rows for the mobile app, projected from the match event logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.modules.demo.models import DemoSchedule
from backend.modules.events.service import score_match
from backend.modules.leagues.models import MatchStream

# Display names for the demo teams (team ids are the stable identifiers).
TEAM_NAMES: dict[str, str] = {
    "club-alpha-1": "Alpha FC",
    "club-alpha-2": "Alpha Rovers",
    "demo-team-3": "Alpha United",
    "demo-team-4": "Alpha City",
}


def team_name(team_id: str) -> str:
    return TEAM_NAMES.get(team_id, team_id)


def fixtures_for_league(session: Session, league_id: str) -> list[dict[str, Any]]:
    """One row per league fixture, ordered by kick-off time then match id.

    Status, scores and version come from the same projection as
    GET /audit/v1/score/{match_id}, so the app never disagrees with it.
    """
    streams = list(
        session.scalars(
            select(MatchStream).where(MatchStream.league_id == league_id)
        ).all()
    )
    match_ids = [stream.match_id for stream in streams]
    schedule: dict[str, str] = {}
    if match_ids:
        schedule = {
            row.match_id: row.scheduled_at
            for row in session.scalars(
                select(DemoSchedule).where(DemoSchedule.match_id.in_(match_ids))
            ).all()
        }

    rows: list[dict[str, Any]] = []
    for stream in streams:
        projection = score_match(session, stream.match_id)
        rows.append(
            {
                "match_id": stream.match_id,
                "home_team_id": stream.home_team_id,
                "home_name": team_name(stream.home_team_id),
                "away_team_id": stream.away_team_id,
                "away_name": team_name(stream.away_team_id),
                "scheduled_at": schedule.get(stream.match_id),
                "status": projection["status"],
                "home_score": projection["home"]["score"],
                "away_score": projection["away"]["score"],
                "version": projection["version"],
            }
        )
    rows.sort(key=lambda row: (row["scheduled_at"] or "9999", row["match_id"]))
    return rows
