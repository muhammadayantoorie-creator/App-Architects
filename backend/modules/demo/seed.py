"""Demo league for the mobile app, rebuilt on startup and on every reset.

Everything goes through the regular league and event services (validation,
sequencing, signatures with salt()), exactly as the HTTP endpoints would.
"""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.demo.models import DemoSchedule
from backend.modules.demo.service import TEAM_NAMES, fixtures_for_league, team_name  # noqa: F401
from backend.modules.events.service import append_event
from backend.modules.leagues.service import create_league
from backend.modules.sports.models import Sport

DEMO_LEAGUE_ID = "demo-league-ui"
DEMO_LEAGUE_NAME = "Alpha Premier League"
DEMO_TENANT_ID = "tenant-alpha"
DEMO_SPORT_ID = "football"
DEMO_TEAMS = ["club-alpha-1", "club-alpha-2", "demo-team-3", "demo-team-4"]

# (match_id, home, away, scheduled_at, final status, scoring sides in order)
DEMO_MATCHES: list[tuple[str, str, str, str, str, list[str]]] = [
    ("demo-match-1", "club-alpha-1", "club-alpha-2", "2026-10-10T15:00:00Z", "completed", ["home", "home", "away"]),
    ("demo-match-2", "demo-team-3", "demo-team-4", "2026-10-12T15:00:00Z", "completed", ["away"]),
    ("demo-match-3", "club-alpha-2", "demo-team-3", "2026-10-14T15:00:00Z", "completed", ["home", "away", "home"]),
    ("demo-match-4", "club-alpha-1", "demo-team-4", "2026-10-17T09:30:00Z", "in_progress", ["home"]),
    ("demo-match-5", "club-alpha-1", "demo-team-3", "2026-10-18T15:00:00Z", "upcoming", []),
    ("demo-match-6", "club-alpha-2", "demo-team-4", "2026-10-21T15:00:00Z", "upcoming", []),
]


def _first_scoring_event(sport: Sport) -> str | None:
    scoring_events = (sport.config or {}).get("scoring_events") or {}
    return next(iter(scoring_events), None)


def seed_demo_league(session: Session, seed: int, _stock: dict) -> None:
    sport = session.get(Sport, DEMO_SPORT_ID)
    if sport is None:
        return

    create_league(
        session,
        {
            "league_id": DEMO_LEAGUE_ID,
            "sport_id": DEMO_SPORT_ID,
            "teams": DEMO_TEAMS,
            "fixtures": [
                {"match_id": match_id, "home": home, "away": away}
                for match_id, home, away, *_rest in DEMO_MATCHES
            ],
            "qualification": {"spots": 2},
            "lots_seed": seed,
        },
        tenant_id=DEMO_TENANT_ID,
        name=DEMO_LEAGUE_NAME,
    )
    session.add_all(
        DemoSchedule(match_id=match_id, scheduled_at=scheduled_at)
        for match_id, _home, _away, scheduled_at, *_rest in DEMO_MATCHES
    )
    session.flush()

    # Signatures need the day salt; without it the fixtures stay upcoming.
    event_type = _first_scoring_event(sport)
    if event_type is None or os.environ.get("DAY1_SALT") is None:
        return

    for index, (match_id, home, away, _when, status, sides) in enumerate(DEMO_MATCHES, start=1):
        if status == "upcoming":
            continue
        bodies = [{"type": "match_start", "payload": {}}]
        bodies += [
            {
                "type": "score",
                "payload": {
                    "team_id": home if side == "home" else away,
                    "event_type": event_type,
                },
            }
            for side in sides
        ]
        if status == "completed":
            bodies.append({"type": "match_end", "payload": {}})
        for number, body in enumerate(bodies, start=1):
            append_event(
                session,
                {"event_id": f"demo-evt-{index}-{number}", "match_id": match_id, **body},
            )


register_reset(50, seed_demo_league)