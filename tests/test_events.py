"""POST /audit/v1/events + GET /audit/v1/score/{match_id} (spec 5.9)."""

from backend.core.signing import sign
from tests.conftest import assert_error


def ev(client, event_id, match_id, kind, payload=None):
    return client.post("/audit/v1/events", json={"event_id": event_id, "match_id": match_id, "type": kind,
                                                 "payload": {} if payload is None else payload})


def init(client, match_id, sport_id="football", home="h", away="a", prefix=None):
    r = ev(client, f"{prefix or match_id}-init", match_id, "match_init",
           {"sport_id": sport_id, "home_team_id": home, "away_team_id": away})
    assert r.status_code == 201, r.text
    return r


def started(client, match_id, sport_id="football", home="h", away="a"):
    init(client, match_id, sport_id, home, away)
    assert ev(client, f"{match_id}-start", match_id, "match_start").status_code == 201


def test_lifecycle_sequence_version_signature(client, reset):
    r = init(client, "mx1")
    assert r.json() == {"event_id": "mx1-init", "match_id": "mx1", "type": "match_init", "sequence": 1,
                        "match_version": 1,
                        "signature": sign("test-salt", "mx1-init",
                                          {"sport_id": "football", "home_team_id": "h", "away_team_id": "a"})}
    assert client.get("/audit/v1/score/mx1").json()["status"] == "upcoming"
    r = ev(client, "mx1-start", "mx1", "match_start")
    assert r.status_code == 201 and r.json()["sequence"] == 2 and r.json()["match_version"] == 2
    payload = {"team_id": "h", "event_type": "goal"}
    r = ev(client, "mx1-g1", "mx1", "score", payload)
    assert r.status_code == 201
    assert r.json()["signature"] == sign("test-salt", "mx1-g1", payload)
    assert ev(client, "mx1-d1", "mx1", "discipline", {"team_id": "a", "points": -3}).status_code == 201
    r = ev(client, "mx1-end", "mx1", "match_end")
    assert r.json()["sequence"] == 5

    score = client.get("/audit/v1/score/mx1").json()
    assert set(score) == {"match_id", "sport_id", "league_id", "status", "outcome", "winner_team_id",
                          "tiebreak_winner_team_id", "home", "away", "version", "events"}
    assert score["status"] == "completed" and score["outcome"] == "home_win"
    assert score["winner_team_id"] == "h" and score["tiebreak_winner_team_id"] is None
    assert score["league_id"] is None and score["sport_id"] == "football" and score["version"] == 5
    assert score["home"] == {"team_id": "h", "score": 1, "wickets": None, "balls": None, "overs": None, "fair_play": 0}
    assert score["away"]["fair_play"] == -3
    first = score["events"][0]
    assert set(first) == {"sequence", "event_id", "type", "payload", "signature", "compensated", "compensated_by"}
    assert [e["sequence"] for e in score["events"]] == [1, 2, 3, 4, 5]
    assert score["events"][2]["signature"] == sign("test-salt", "mx1-g1", payload)


def test_idempotent_replay_and_duplicate_id(client, reset):
    started(client, "mx2")
    body = {"event_id": "mx2-g", "match_id": "mx2", "type": "score", "payload": {"team_id": "h", "event_type": "goal"}}
    first = client.post("/audit/v1/events", json=body)
    assert first.status_code == 201
    again = client.post("/audit/v1/events", json=body)
    assert again.status_code == 200 and again.json() == first.json()
    assert client.get("/audit/v1/score/mx2").json()["version"] == 3
    body["payload"] = {"team_id": "a", "event_type": "goal"}
    assert_error(client.post("/audit/v1/events", json=body), 409, "DUPLICATE_EVENT_ID")


def test_errors(client, reset):
    assert_error(ev(client, "z1", "nope", "match_start"), 404, "MATCH_NOT_FOUND")
    assert_error(ev(client, "z2", "nope", "teleport"), 400, "UNKNOWN_EVENT_TYPE")
    assert_error(ev(client, "z3", "mz", "match_init", {"sport_id": "curling", "home_team_id": "h", "away_team_id": "a"}),
                 404, "SPORT_NOT_FOUND")
    init(client, "mz")
    assert_error(ev(client, "z4", "mz", "match_init", {"sport_id": "football", "home_team_id": "h", "away_team_id": "a"}),
                 409, "MATCH_EXISTS")
    assert_error(ev(client, "z5", "mz", "score", {"team_id": "h", "event_type": "goal"}), 409, "MATCH_NOT_IN_PROGRESS")
    assert_error(ev(client, "z6", "mz", "match_end"), 409, "ILLEGAL_TRANSITION")
    assert ev(client, "z7", "mz", "match_start").status_code == 201
    assert_error(ev(client, "z8", "mz", "match_start"), 409, "ILLEGAL_TRANSITION")
    err = assert_error(ev(client, "z9", "mz", "score", {"team_id": "x", "event_type": "goal"}), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["payload.team_id"]
    assert_error(ev(client, "z10", "mz", "score", {"team_id": "h", "event_type": "touchdown"}), 400, "UNKNOWN_EVENT_TYPE")
    err = assert_error(ev(client, "z11", "mz", "discipline", {"team_id": "h", "points": "2"}), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["payload.points"]
    err = assert_error(client.post("/audit/v1/events", json={"match_id": "mz", "type": "score"}), 400, "VALIDATION_ERROR")
    assert {"event_id", "payload"} <= set(err["details"]["fields"])
    assert ev(client, "z12", "mz", "match_end").status_code == 201
    assert_error(ev(client, "z13", "mz", "tiebreak_winner", {"team_id": "h"}), 409, "MATCH_NOT_IN_PROGRESS")


def test_tie_not_allowed_resolved_by_tiebreak(client, reset):
    started(client, "bk1", sport_id="basketball")
    assert ev(client, "bk1-s1", "bk1", "score", {"team_id": "h", "event_type": "two_pointer"}).status_code == 201
    assert ev(client, "bk1-s2", "bk1", "score", {"team_id": "a", "event_type": "two_pointer"}).status_code == 201
    assert_error(ev(client, "bk1-end", "bk1", "match_end"), 409, "TIE_NOT_ALLOWED")
    assert ev(client, "bk1-tb", "bk1", "tiebreak_winner", {"team_id": "a"}).status_code == 201
    assert ev(client, "bk1-end2", "bk1", "match_end").status_code == 201
    score = client.get("/audit/v1/score/bk1").json()
    assert score["outcome"] == "away_win" and score["winner_team_id"] == "a"
    assert score["tiebreak_winner_team_id"] == "a"
    assert score["home"]["score"] == 2 and score["away"]["score"] == 2


def test_compensation(client, reset):
    started(client, "cp1")
    assert ev(client, "cp1-g1", "cp1", "score", {"team_id": "h", "event_type": "goal"}).status_code == 201
    assert ev(client, "cp1-end", "cp1", "match_end").status_code == 201
    assert client.get("/audit/v1/score/cp1").json()["outcome"] == "home_win"
    r = ev(client, "cp1-c1", "cp1", "compensation", {"compensates": "cp1-g1", "reason": "VAR"})
    assert r.status_code == 201 and r.json()["sequence"] == 5
    score = client.get("/audit/v1/score/cp1").json()
    assert score["home"]["score"] == 0 and score["outcome"] == "draw" and score["winner_team_id"] is None
    target = next(e for e in score["events"] if e["event_id"] == "cp1-g1")
    assert target["compensated"] is True and target["compensated_by"] == "cp1-c1"
    comp = next(e for e in score["events"] if e["event_id"] == "cp1-c1")
    assert comp["compensated"] is False and comp["compensated_by"] is None

    assert_error(ev(client, "cp1-c2", "cp1", "compensation", {"compensates": "cp1-g1", "reason": "again"}),
                 409, "INVALID_COMPENSATION")
    assert_error(ev(client, "cp1-c3", "cp1", "compensation", {"compensates": "cp1-start", "reason": "x"}),
                 409, "INVALID_COMPENSATION")
    assert_error(ev(client, "cp1-c4", "cp1", "compensation", {"compensates": "missing-evt", "reason": "x"}),
                 404, "EVENT_NOT_FOUND")
    started(client, "cp2")
    assert ev(client, "cp2-g1", "cp2", "score", {"team_id": "h", "event_type": "goal"}).status_code == 201
    assert_error(ev(client, "cp1-c5", "cp1", "compensation", {"compensates": "cp2-g1", "reason": "x"}),
                 409, "INVALID_COMPENSATION")


def test_compensated_tiebreak_leaves_match_undecided(client, reset):
    started(client, "bk2", sport_id="basketball")
    assert ev(client, "bk2-tb", "bk2", "tiebreak_winner", {"team_id": "h"}).status_code == 201
    assert ev(client, "bk2-end", "bk2", "match_end").status_code == 201
    assert ev(client, "bk2-c", "bk2", "compensation", {"compensates": "bk2-tb", "reason": "x"}).status_code == 201
    score = client.get("/audit/v1/score/bk2").json()
    assert score["outcome"] == "undecided" and score["winner_team_id"] is None


def test_innings_complete_and_overs(client, reset):
    sport = {
        "sport_id": "tiny-innings", "name": "Tiny", "scoring_model": "innings",
        "periods": {"innings_per_team": 1, "overs_per_innings": 1, "balls_per_over": 2, "wickets_per_innings": 2},
        "scoring_events": {"one": {"runs": 1, "legal_ball": True, "wicket": False},
                           "wd": {"runs": 1, "legal_ball": False, "wicket": False}},
        "draw_allowed": True, "overtime": {"policy": "none"},
        "roster": {"min_squad_size": 1, "max_squad_size": 2, "required_positions": {}},
    }
    assert client.post("/audit/v1/sports", json=sport).status_code == 201
    started(client, "ti1", sport_id="tiny-innings")
    assert ev(client, "ti1-1", "ti1", "score", {"team_id": "h", "event_type": "one"}).status_code == 201
    score = client.get("/audit/v1/score/ti1").json()
    assert score["home"]["balls"] == 1 and score["home"]["overs"] == "0.1" and score["home"]["wickets"] == 0
    assert score["away"]["overs"] == "0.0"
    assert ev(client, "ti1-2", "ti1", "score", {"team_id": "h", "event_type": "wd"}).status_code == 201
    assert ev(client, "ti1-3", "ti1", "score", {"team_id": "h", "event_type": "one"}).status_code == 201
    score = client.get("/audit/v1/score/ti1").json()
    assert score["home"]["score"] == 3 and score["home"]["overs"] == "1.0"
    assert_error(ev(client, "ti1-4", "ti1", "score", {"team_id": "h", "event_type": "wd"}), 409, "INNINGS_COMPLETE")
    # Compensated balls do not count.
    assert ev(client, "ti1-c", "ti1", "compensation", {"compensates": "ti1-3", "reason": "x"}).status_code == 201
    assert ev(client, "ti1-5", "ti1", "score", {"team_id": "h", "event_type": "one"}).status_code == 201
    assert ev(client, "ti1-6", "ti1", "score", {"team_id": "a", "event_type": "one"}).status_code == 201


def test_round_series_already_decided(client, reset):
    started(client, "es1", sport_id="esports")
    for i in range(2):
        assert ev(client, f"es1-{i}", "es1", "score", {"team_id": "h", "event_type": "round_win"}).status_code == 201
    assert_error(ev(client, "es1-x", "es1", "score", {"team_id": "a", "event_type": "round_win"}),
                 409, "SERIES_ALREADY_DECIDED")
    score = client.get("/audit/v1/score/es1").json()
    assert score["home"]["score"] == 2 and score["home"]["wickets"] is None


def test_league_fixture_accepts_init_and_start(client, reset):
    league = {"league_id": "lg-ev", "sport_id": "football", "teams": ["t1", "t2"],
              "fixtures": [{"match_id": "f1", "home": "t1", "away": "t2"}, {"match_id": "f2", "home": "t2", "away": "t1"}],
              "qualification": {"spots": 1}}
    assert client.post("/audit/v1/leagues", json=league).status_code == 201
    r = ev(client, "f1-init", "f1", "match_init",
           {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2", "league_id": "lg-ev"})
    assert r.status_code == 201 and r.json()["sequence"] == 1
    assert_error(ev(client, "f1-init2", "f1", "match_init",
                    {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"}), 409, "MATCH_EXISTS")
    r = ev(client, "f2-start", "f2", "match_start")
    assert r.status_code == 201 and r.json()["sequence"] == 1
    assert client.get("/audit/v1/score/f2").json()["status"] == "in_progress"
