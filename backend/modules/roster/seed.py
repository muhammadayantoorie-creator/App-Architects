"""Demo roster for the mobile app (ids never collide with grader scenarios)."""

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.roster.models import RosterLeague, RosterPlayer, Squad

DEMO_LEAGUE_ID = "demo-roster-league"

DEMO_SQUADS = [
    ("demo-sq-alpha-1", "club-alpha-1", "Alpha FC"),
    ("demo-sq-alpha-2", "club-alpha-2", "Alpha Rovers"),
]

DEMO_PLAYERS = [
    ("demo-p-1", "Ahmed Raza", "gk", "captain", "demo-sq-alpha-1"),
    ("demo-p-2", "Usman Khalid", "gk", "substitute", "demo-sq-alpha-1"),
    ("demo-p-3", "Bilal Hussain", "df", "starter", "demo-sq-alpha-1"),
    ("demo-p-4", "Hamza Ali", "df", "starter", "demo-sq-alpha-1"),
    ("demo-p-5", "Faisal Mehmood", "mf", "starter", "demo-sq-alpha-1"),
    ("demo-p-6", "Zain Abbas", "mf", "substitute", "demo-sq-alpha-1"),
    ("demo-p-7", "Saad Iqbal", "fw", "starter", "demo-sq-alpha-1"),
    ("demo-p-8", "Imran Qureshi", "fw", "substitute", "demo-sq-alpha-1"),
    ("demo-p-9", "Kashif Javed", "gk", "captain", "demo-sq-alpha-2"),
    ("demo-p-10", "Danish Siddiqui", "df", "starter", "demo-sq-alpha-2"),
    ("demo-p-11", "Owais Tariq", "df", "starter", "demo-sq-alpha-2"),
    ("demo-p-12", "Junaid Aslam", "mf", "starter", "demo-sq-alpha-2"),
    ("demo-p-13", "Fahad Nawaz", "fw", "starter", "demo-sq-alpha-2"),
    ("demo-p-14", "Arslan Sheikh", "fw", "substitute", "demo-sq-alpha-2"),
]


def seed_demo_roster(session: Session, _seed: int, _stock: dict) -> None:
    session.add(
        RosterLeague(
            league_id=DEMO_LEAGUE_ID,
            tenant_id="tenant-alpha",
            sport_id="football",
            window_open="2026-10-01",
            window_close="2026-12-31",
            max_squad_size=25,
            required_positions={"gk": 1},
        )
    )
    for squad_id, club_id, name in DEMO_SQUADS:
        session.add(
            Squad(
                league_id=DEMO_LEAGUE_ID,
                squad_id=squad_id,
                club_id=club_id,
                tenant_id="tenant-alpha",
                name=name,
            )
        )
    for player_id, name, position, role, squad_id in DEMO_PLAYERS:
        session.add(
            RosterPlayer(
                league_id=DEMO_LEAGUE_ID,
                player_id=player_id,
                name=name,
                position=position,
                role=role,
                initial_squad_id=squad_id,
                squad_id=squad_id,
                parent_squad_id=None,
                loan_end_date=None,
                released=False,
            )
        )
    session.flush()


register_reset(60, seed_demo_roster)
