"""POST /audit/v1/leagues (spec 5.8) and the mobile demo league seed."""

import copy

from backend.core.signing import salt, sign
from tests.conftest import assert_error

LEAGUE = {
    "league_id": "lg-1",
    "sport_id": "football",
    "teams": ["t1", "t2", "t3", "t4"],
    "fixtures": [{"match_id": "m1", "home": "t1", "away": "t2"}, {"match_id": "m2", "home": "t3", "away": "t4"}],
    "points": {"win": 3, "draw": 1, "loss": 0},
    "tie_break_order": ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"],
    "qualification": {"spots": 2},
    "lots_seed": 42,
}


def _fields(response):
    return assert_error(response, 400, "VALIDATION_ERROR")["details"]["fields"]


def test_create_league_exact_body(client, reset):
    r = client.post("/audit/v1/leagues", json=LEAGUE)
    assert r.status_code == 201, r.text
    assert r.json() == {"league_id": "lg-1", "status": "created", "team_count": 4, "fixture_count": 2}
    score = client.get("/audit/v1/score/m1").json()
    assert score["status"] == "upcoming" and score["league_id"] == "lg-1" and score["version"] == 0


def test_optional_fields_default(client, reset):
    body = {k: v for k, v in LEAGUE.items() if k not in ("points", "tie_break_order", "lots_seed")}
    assert client.post("/audit/v1/leagues", json=body).status_code == 201


def test_sport_not_found_before_conflicts(client, reset):
    assert client.post("/audit/v1/leagues", json=LEAGUE).status_code == 201
    body = copy.deepcopy(LEAGUE)
    body["sport_id"] = "curling"
    assert_error(client.post("/audit/v1/leagues", json=body), 404, "SPORT_NOT_FOUND")


def test_league_and_match_exists(client, reset):
    assert client.post("/audit/v1/leagues", json=LEAGUE).status_code == 201
    assert_error(client.post("/audit/v1/leagues", json=LEAGUE), 409, "LEAGUE_EXISTS")
    body = copy.deepcopy(LEAGUE)
    body["league_id"] = "lg-2"
    assert_error(client.post("/audit/v1/leagues", json=body), 409, "MATCH_EXISTS")
    body["fixtures"] = [{"match_id": "mx", "home": "t1", "away": "t2"}, {"match_id": "mx", "home": "t3", "away": "t4"}]
    assert_error(client.post("/audit/v1/leagues", json=body), 409, "MATCH_EXISTS")
    # A stream created by match_init also blocks the id.
    r = client.post("/audit/v1/events", json={"event_id": "e-init", "match_id": "solo-1", "type": "match_init",
                                              "payload": {"sport_id": "football", "home_team_id": "a", "away_team_id": "b"}})
    assert r.status_code == 201, r.text
    body["fixtures"] = [{"match_id": "solo-1", "home": "t1", "away": "t2"}]
    assert_error(client.post("/audit/v1/leagues", json=body), 409, "MATCH_EXISTS")


def test_validation(client, reset):
    cases = [
        ({"teams": ["t1"]}, "teams"),
        ({"teams": ["t%d" % i for i in range(41)]}, "teams"),
        ({"teams": ["t1", "t1", "t2"]}, "teams"),
        ({"fixtures": [{"match_id": "m1", "home": "t1", "away": "t9"}]}, "fixtures.0.away"),
        ({"fixtures": [{"match_id": "m1", "home": "t1", "away": "t1"}]}, "fixtures.0.away"),
        ({"qualification": {"spots": 0}}, "qualification.spots"),
        ({"qualification": {"spots": 5}}, "qualification.spots"),
        ({"qualification": None}, "qualification"),
        ({"points": {"win": "3"}}, "points.win"),
        ({"lots_seed": "42"}, "lots_seed"),
        ({"league_id": "bad|id"}, "league_id"),
    ]
    for override, field in cases:
        body = copy.deepcopy(LEAGUE)
        body.update(override)
        assert field in _fields(client.post("/audit/v1/leagues", json=body)), override
    for missing in ("league_id", "sport_id", "teams", "fixtures", "qualification"):
        body = copy.deepcopy(LEAGUE)
        body.pop(missing)
        assert missing in _fields(client.post("/audit/v1/leagues", json=body)), missing


def test_demo_league_seed(client, reset):
    from backend.core.db import SessionLocal
    from backend.modules.demo.seed import TEAM_NAMES, fixtures_for_league
    from backend.modules.leagues.models import League

    with SessionLocal() as session:
        league = session.get(League, "demo-league-ui")
        assert league.name == "Alpha Premier League" and league.tenant_id == "tenant-alpha"
        rows = fixtures_for_league(session, "demo-league-ui")
    assert [r["match_id"] for r in rows] == [f"demo-match-{i}" for i in range(1, 7)]
    assert [r["status"] for r in rows] == ["completed"] * 3 + ["in_progress"] + ["upcoming"] * 2
    live = rows[3]
    assert live["scheduled_at"] == "2026-10-17T09:30:00Z"
    assert live["home_team_id"] == "club-alpha-1" and live["home_name"] == "Alpha FC"
    assert live["home_score"] == 1 and live["away_score"] == 0 and live["version"] == 2
    assert TEAM_NAMES["demo-team-4"] == "Alpha City"
    for row in rows:
        assert set(row) == {"match_id", "home_team_id", "home_name", "away_team_id", "away_name",
                            "scheduled_at", "status", "home_score", "away_score", "version"}

    score = client.get("/audit/v1/score/demo-match-1").json()
    assert score["outcome"] == "home_win"
    for event in score["events"]:
        assert event["signature"] == sign(salt(), event["event_id"], event["payload"])
    table = client.get("/audit/v1/standings/demo-league-ui").json()["table"]
    assert len(table) == 4 and sum(row["played"] for row in table) == 6

    # Reset rebuilds exactly the same demo state.
    client.post("/audit/v1/reset", json={})
    assert client.get("/audit/v1/score/demo-match-1").json() == score
