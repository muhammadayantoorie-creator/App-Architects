"""Baseline sports inserted through the regular sport validation path."""

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.sports.service import create_sport

BASELINE_SPORTS = [
    {
        "sport_id": "football",
        "name": "Football",
        "scoring_model": "event",
        "periods": {"count": 2, "duration_minutes": 45},
        "scoring_events": {"goal": {"points": 1}},
        "draw_allowed": True,
        "overtime": {"policy": "none"},
        "roster": {
            "min_squad_size": 11,
            "max_squad_size": 25,
            "required_positions": {"gk": 1},
        },
    },
    {
        "sport_id": "basketball",
        "name": "Basketball",
        "scoring_model": "event",
        "periods": {"count": 4, "duration_minutes": 12},
        "scoring_events": {
            "free_throw": {"points": 1},
            "two_pointer": {"points": 2},
            "three_pointer": {"points": 3},
        },
        "draw_allowed": False,
        "overtime": {"policy": "extra_time", "duration_minutes": 5},
        "roster": {
            "min_squad_size": 5,
            "max_squad_size": 15,
            "required_positions": {},
        },
    },
    {
        "sport_id": "cricket",
        "name": "Cricket",
        "scoring_model": "innings",
        "periods": {
            "innings_per_team": 1,
            "overs_per_innings": 20,
            "balls_per_over": 6,
            "wickets_per_innings": 10,
        },
        "scoring_events": {
            "dot_ball": {"runs": 0, "legal_ball": True, "wicket": False},
            "single": {"runs": 1, "legal_ball": True, "wicket": False},
            "two": {"runs": 2, "legal_ball": True, "wicket": False},
            "four": {"runs": 4, "legal_ball": True, "wicket": False},
            "six": {"runs": 6, "legal_ball": True, "wicket": False},
            "wide": {"runs": 1, "legal_ball": False, "wicket": False},
            "no_ball": {"runs": 1, "legal_ball": False, "wicket": False},
            "wicket": {"runs": 0, "legal_ball": True, "wicket": True},
        },
        "draw_allowed": True,
        "overtime": {"policy": "super_over"},
        "roster": {
            "min_squad_size": 11,
            "max_squad_size": 18,
            "required_positions": {"wicketkeeper": 1},
        },
    },
    {
        "sport_id": "esports",
        "name": "Esports",
        "scoring_model": "round",
        "periods": {"best_of": 3},
        "scoring_events": {"round_win": {"rounds": 1}},
        "draw_allowed": False,
        "overtime": {"policy": "none"},
        "roster": {
            "min_squad_size": 5,
            "max_squad_size": 8,
            "required_positions": {},
        },
    },
]


def seed_sports(session: Session, _seed: int, _stock: dict) -> None:
    for sport in BASELINE_SPORTS:
        create_sport(session, sport, commit=False)


register_reset(20, seed_sports)
