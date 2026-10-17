"""GET /audit/v1/standings/{league_id} (spec 5.10, edge cases 4 and 5)."""

from tests.conftest import assert_error

ROW_KEYS = {"rank", "team_id", "played", "won", "drawn", "lost", "scored", "conceded", "diff", "points",
            "fair_play", "status", "resolved_by"}


def ev(client, event_id, match_id, kind, payload=None):
    r = client.post("/audit/v1/events", json={"event_id": event_id, "match_id": match_id, "type": kind,
                                              "payload": payload or {}})
    assert r.status_code == 201, r.text
    return r


def play(client, match_id, scorers, event_type="goal", end=True):
    ev(client, f"{match_id}-start", match_id, "match_start")
    for i, (team_id, kind) in enumerate(scorers):
        ev(client, f"{match_id}-s{i}", match_id, "score", {"team_id": team_id, "event_type": kind or event_type})
    if end:
        ev(client, f"{match_id}-end", match_id, "match_end")


def league(client, league_id, teams, fixtures, spots=2, sport_id="football", **extra):
    body = {"league_id": league_id, "sport_id": sport_id, "teams": teams,
            "fixtures": [{"match_id": m, "home": h, "away": a} for m, h, a in fixtures],
            "qualification": {"spots": spots}, **extra}
    r = client.post("/audit/v1/leagues", json=body)
    assert r.status_code == 201, r.text


def standings(client, league_id):
    r = client.get(f"/audit/v1/standings/{league_id}")
    assert r.status_code == 200, r.text
    return r.json()


def test_not_found(client, reset):
    assert_error(client.get("/audit/v1/standings/none"), 404, "LEAGUE_NOT_FOUND")


def test_shape_and_h2h_zeros(client, reset):
    league(client, "lg-s", ["a", "b", "c"], [("s1", "a", "b")], spots=1)
    data = standings(client, "lg-s")
    assert set(data) == {"league_id", "sport_id", "qualification_spots", "table", "h2h"}
    assert data["league_id"] == "lg-s" and data["sport_id"] == "football" and data["qualification_spots"] == 1
    assert [row["rank"] for row in data["table"]] == [1, 2, 3]
    for row in data["table"]:
        assert set(row) == ROW_KEYS
        assert row["played"] == 0 and row["points"] == 0
    for team in "abc":
        assert set(data["h2h"][team]) == set("abc") - {team}
        for other in data["h2h"][team].values():
            assert other == {"played": 0, "points": 0, "scored": 0, "conceded": 0}


def test_draw_lots_spec_vector(client, reset):
    league(client, "lg-1", ["t1", "t2", "t3"], [("dl1", "t1", "t2")], spots=1, lots_seed=42)
    table = standings(client, "lg-1")["table"]
    assert [row["team_id"] for row in table] == ["t1", "t3", "t2"]
    assert all(row["resolved_by"] == "draw_lots" for row in table)


def test_default_lots_seed_is_last_reset_seed(client):
    client.post("/audit/v1/reset", json={"seed": 42})
    league(client, "lg-1", ["t1", "t2", "t3"], [], spots=1)
    assert [row["team_id"] for row in standings(client, "lg-1")["table"]] == ["t1", "t3", "t2"]


def test_three_way_tie_h2h_mini_league(client, reset):
    teams = ["t1", "t2", "t3", "t4"]
    fixtures = [("w1", "t1", "t2"), ("w2", "t2", "t3"), ("w3", "t3", "t1"),
                ("w4", "t1", "t4"), ("w5", "t2", "t4"), ("w6", "t3", "t4")]
    league(client, "lg-tie", teams, fixtures, spots=2)
    play(client, "w1", [("t1", None)])                              # t1 1-0 t2
    play(client, "w2", [("t2", None)] * 3)                          # t2 3-0 t3
    play(client, "w3", [("t3", None)] * 2)                          # t3 2-0 t1
    for match_id, home in (("w4", "t1"), ("w5", "t2"), ("w6", "t3")):
        play(client, match_id, [(home, None)])                      # each 1-0 over t4
    data = standings(client, "lg-tie")
    table = {row["team_id"]: row for row in data["table"]}
    assert [row["team_id"] for row in data["table"]] == ["t2", "t3", "t1", "t4"]
    assert table["t2"]["resolved_by"] == "h2h_diff"
    assert table["t3"]["resolved_by"] is not None and table["t1"]["resolved_by"] is not None
    assert table["t4"]["resolved_by"] is None
    assert table["t2"] | {"status": None} == {
        "rank": 1, "team_id": "t2", "played": 3, "won": 2, "drawn": 0, "lost": 1, "scored": 4, "conceded": 1,
        "diff": 3, "points": 6, "fair_play": 0, "status": None, "resolved_by": "h2h_diff"}
    assert data["h2h"]["t1"]["t2"] == {"played": 1, "points": 3, "scored": 1, "conceded": 0}
    assert data["h2h"]["t2"]["t1"] == {"played": 1, "points": 0, "scored": 0, "conceded": 1}
    assert table["t4"]["status"] == "eliminated"


def test_qualification_statuses(client, reset):
    league(client, "lg-q", ["a", "b", "c"], [("q1", "a", "b"), ("q2", "a", "c"), ("q3", "b", "c")], spots=1)
    assert {row["status"] for row in standings(client, "lg-q")["table"]} == {"still_possible"}
    play(client, "q1", [("a", None)])
    play(client, "q2", [("a", None)])
    table = {row["team_id"]: row for row in standings(client, "lg-q")["table"]}
    assert table["a"]["status"] == "clinched"
    assert table["b"]["status"] == "eliminated" and table["c"]["status"] == "eliminated"


def test_compensation_on_completed_match_recomputes(client, reset):
    league(client, "lg-c", ["x", "y"], [("c1", "x", "y")], spots=1)
    play(client, "c1", [("x", None)])
    before = {row["team_id"]: row for row in standings(client, "lg-c")["table"]}
    assert before["x"]["points"] == 3 and before["x"]["won"] == 1
    ev(client, "c1-comp", "c1", "compensation", {"compensates": "c1-s0", "reason": "offside"})
    after = {row["team_id"]: row for row in standings(client, "lg-c")["table"]}
    assert after["x"]["points"] == 1 and after["y"]["points"] == 1
    assert after["x"]["drawn"] == 1 and after["x"]["scored"] == 0


def test_in_progress_and_undecided_do_not_count(client, reset):
    league(client, "lg-u", ["p", "q"], [("u1", "p", "q"), ("u2", "q", "p")], spots=1, sport_id="basketball")
    play(client, "u1", [("p", "two_pointer")], end=False)
    ev(client, "u2-start", "u2", "match_start")
    ev(client, "u2-tb", "u2", "tiebreak_winner", {"team_id": "q"})
    ev(client, "u2-end", "u2", "match_end")
    ev(client, "u2-comp", "u2", "compensation", {"compensates": "u2-tb", "reason": "x"})
    assert client.get("/audit/v1/score/u2").json()["outcome"] == "undecided"
    for row in standings(client, "lg-u")["table"]:
        assert row["played"] == 0 and row["points"] == 0 and row["scored"] == 0


def test_fair_play_and_custom_points(client, reset):
    league(client, "lg-f", ["f1", "f2"], [("fp1", "f1", "f2")], spots=1,
           points={"win": 2, "draw": 1, "loss": -1})
    ev(client, "fp1-start", "fp1", "match_start")
    ev(client, "fp1-g", "fp1", "score", {"team_id": "f2", "event_type": "goal"})
    ev(client, "fp1-d", "fp1", "discipline", {"team_id": "f2", "points": -2})
    ev(client, "fp1-end", "fp1", "match_end")
    table = {row["team_id"]: row for row in standings(client, "lg-f")["table"]}
    assert table["f2"]["points"] == 2 and table["f1"]["points"] == -1
    assert table["f2"]["fair_play"] == -2 and table["f2"]["rank"] == 1


def test_net_run_rate_innings(client, reset):
    sport = {
        "sport_id": "nrr-sport", "name": "NRR", "scoring_model": "innings",
        "periods": {"innings_per_team": 1, "overs_per_innings": 3, "balls_per_over": 2, "wickets_per_innings": 2},
        "scoring_events": {"one": {"runs": 1, "legal_ball": True, "wicket": False},
                           "out": {"runs": 0, "legal_ball": True, "wicket": True}},
        "draw_allowed": True, "overtime": {"policy": "none"},
        "roster": {"min_squad_size": 1, "max_squad_size": 2, "required_positions": {}},
    }
    assert client.post("/audit/v1/sports", json=sport).status_code == 201
    league(client, "lg-n", ["h", "a"], [("n1", "h", "a")], spots=1, sport_id="nrr-sport")
    # h: 3 runs off 3 balls (1.5 overs). a: 1 run, all out after 3 balls -> full 3 overs.
    play(client, "n1", [("h", "one")] * 3 + [("a", "one"), ("a", "out"), ("a", "out")])
    score = client.get("/audit/v1/score/n1").json()
    assert score["home"]["overs"] == "1.1" and score["away"]["wickets"] == 2
    table = {row["team_id"]: row for row in standings(client, "lg-n")["table"]}
    assert table["h"]["diff"] == 1.667 and table["a"]["diff"] == -1.667
    assert table["h"]["scored"] == 3 and table["a"]["conceded"] == 3
