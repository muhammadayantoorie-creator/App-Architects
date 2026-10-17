"""POST /audit/v1/sports (spec 5.6) and mystery-sport usability."""

import copy

from tests.conftest import assert_error

KABADDI = {
    "sport_id": "kabaddi",
    "name": "Kabaddi",
    "scoring_model": "event",
    "periods": {"count": 2, "duration_minutes": 20},
    "scoring_events": {
        "raid_point": {"points": 1},
        "tackle_point": {"points": 1},
        "all_out": {"points": 2},
    },
    "draw_allowed": True,
    "overtime": {"policy": "none"},
    "tie_break_order": ["h2h_points", "overall_diff", "scored", "draw_lots"],
    "roster": {"min_squad_size": 7, "max_squad_size": 12, "required_positions": {"raider": 2}},
}

INNINGS = {
    "sport_id": "mini-innings",
    "name": "Mini innings",
    "scoring_model": "innings",
    "periods": {"innings_per_team": 1, "overs_per_innings": 1, "balls_per_over": 2, "wickets_per_innings": 1},
    "scoring_events": {
        "run_one": {"runs": 1, "legal_ball": True, "wicket": False},
        "extra": {"runs": 1, "legal_ball": False, "wicket": False},
        "out": {"runs": 0, "legal_ball": True, "wicket": True},
    },
    "draw_allowed": True,
    "overtime": {"policy": "super_over"},
    "roster": {"min_squad_size": 2, "max_squad_size": 4, "required_positions": {}},
}

ROUND = {
    "sport_id": "duel-bo3",
    "name": "Duel",
    "scoring_model": "round",
    "periods": {"best_of": 3},
    "scoring_events": {"round_taken": {"rounds": 1}},
    "draw_allowed": False,
    "overtime": {"policy": "golden_score", "duration_minutes": 0},
    "roster": {"min_squad_size": 1, "max_squad_size": 3, "required_positions": {}},
}


def _fields(response):
    return assert_error(response, 400, "VALIDATION_ERROR")["details"]["fields"]


def test_create_event_model_sport(client, reset):
    r = client.post("/audit/v1/sports", json=KABADDI)
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"sport_id", "status", "config"}
    assert body["sport_id"] == "kabaddi" and body["status"] == "created"
    config = body["config"]
    assert config["scoring_model"] == "event"
    assert config["periods"] == {"count": 2, "duration_minutes": 20}
    assert config["scoring_events"] == KABADDI["scoring_events"]
    assert config["tie_break_order"][-1] == "draw_lots"
    assert config["roster"] == KABADDI["roster"]


def test_create_innings_and_round_models(client, reset):
    for sport in (INNINGS, ROUND):
        r = client.post("/audit/v1/sports", json=sport)
        assert r.status_code == 201, r.text
        assert r.json()["config"]["periods"] == sport["periods"]
        assert r.json()["config"]["scoring_events"] == sport["scoring_events"]


def test_default_tie_break_order_and_draw_lots_last(client, reset):
    body = copy.deepcopy(KABADDI)
    body.pop("tie_break_order")
    full = client.post("/audit/v1/sports", json=body).json()["config"]["tie_break_order"]
    assert full == ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]
    body = copy.deepcopy(ROUND)
    body["sport_id"] = "duel-two"
    body["tie_break_order"] = ["draw_lots", "scored"]
    order = client.post("/audit/v1/sports", json=body).json()["config"]["tie_break_order"]
    assert order == ["scored", "draw_lots"]


def test_duplicate_sport_is_409(client, reset):
    assert client.post("/audit/v1/sports", json=KABADDI).status_code == 201
    assert_error(client.post("/audit/v1/sports", json=KABADDI), 409, "SPORT_EXISTS")
    baseline = copy.deepcopy(KABADDI)
    baseline["sport_id"] = "football"
    assert_error(client.post("/audit/v1/sports", json=baseline), 409, "SPORT_EXISTS")


def test_sql_injection_sport_id_is_400(client, reset):
    body = copy.deepcopy(KABADDI)
    body["sport_id"] = "x'; DROP TABLE sports;--"
    assert "sport_id" in _fields(client.post("/audit/v1/sports", json=body))
    # Table is intact.
    assert client.post("/audit/v1/sports", json=KABADDI).status_code == 201


def test_validation_fields(client, reset):
    cases = [
        ({"sport_id": "A"}, "sport_id"),
        ({"name": ""}, "name"),
        ({"name": "x" * 81}, "name"),
        ({"scoring_model": "points"}, "scoring_model"),
        ({"periods": {"count": 0, "duration_minutes": 20}}, "periods.count"),
        ({"periods": {"count": 2}}, "periods.duration_minutes"),
        ({"scoring_events": {}}, "scoring_events"),
        ({"scoring_events": {"raid": {"points": 0}}}, "scoring_events.raid.points"),
        ({"scoring_events": {"Bad-Key": {"points": 1}}}, "scoring_events"),
        ({"draw_allowed": "yes"}, "draw_allowed"),
        ({"overtime": {"policy": "sudden"}}, "overtime.policy"),
        ({"overtime": {"policy": "none", "duration_minutes": -1}}, "overtime.duration_minutes"),
        ({"tie_break_order": ["scored", "scored"]}, "tie_break_order.1"),
        ({"tie_break_order": ["luck"]}, "tie_break_order.0"),
        ({"roster": {"min_squad_size": 5, "max_squad_size": 2, "required_positions": {}}}, "roster.min_squad_size"),
    ]
    for override, field in cases:
        body = copy.deepcopy(KABADDI)
        body.update(override)
        assert field in _fields(client.post("/audit/v1/sports", json=body)), override

    body = copy.deepcopy(INNINGS)
    body["periods"] = {"innings_per_team": 1, "overs_per_innings": 0, "balls_per_over": 6, "wickets_per_innings": 10}
    body["scoring_events"] = {"dot": {"runs": -1, "legal_ball": "y", "wicket": False}}
    fields = _fields(client.post("/audit/v1/sports", json=body))
    assert {"periods.overs_per_innings", "scoring_events.dot.runs", "scoring_events.dot.legal_ball"} <= set(fields)

    body = copy.deepcopy(ROUND)
    body["periods"] = {"best_of": 2}
    body["scoring_events"] = {"round_taken": {"rounds": 0}}
    fields = _fields(client.post("/audit/v1/sports", json=body))
    assert {"periods.best_of", "scoring_events.round_taken.rounds"} <= set(fields)

    for missing in ("sport_id", "name", "scoring_model", "periods", "scoring_events", "draw_allowed"):
        body = copy.deepcopy(KABADDI)
        body.pop(missing)
        assert missing in _fields(client.post("/audit/v1/sports", json=body)), missing

    assert _fields(client.post("/audit/v1/sports", json=[1, 2])) == ["body"]
    r = client.post("/audit/v1/sports", content="{bad json", headers={"Content-Type": "application/json"})
    assert_error(r, 400, "VALIDATION_ERROR")


def test_mystery_sport_usable_everywhere(client, reset):
    assert client.post("/audit/v1/sports", json=KABADDI).status_code == 201
    league = {
        "league_id": "lg-kabaddi", "sport_id": "kabaddi", "teams": ["k1", "k2"],
        "fixtures": [{"match_id": "km-1", "home": "k1", "away": "k2"}], "qualification": {"spots": 1},
    }
    assert client.post("/audit/v1/leagues", json=league).status_code == 201
    for i, (kind, payload) in enumerate([
        ("match_start", {}),
        ("score", {"team_id": "k1", "event_type": "all_out"}),
        ("score", {"team_id": "k2", "event_type": "raid_point"}),
        ("match_end", {}),
    ], start=1):
        r = client.post("/audit/v1/events", json={"event_id": f"k-{i}", "match_id": "km-1", "type": kind, "payload": payload})
        assert r.status_code == 201, r.text
    score = client.get("/audit/v1/score/km-1").json()
    assert score["home"]["score"] == 2 and score["away"]["score"] == 1
    assert score["outcome"] == "home_win"
    table = client.get("/audit/v1/standings/lg-kabaddi").json()["table"]
    assert [row["team_id"] for row in table] == ["k1", "k2"]
    assert table[0]["points"] == 3
