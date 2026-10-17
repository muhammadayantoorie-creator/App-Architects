import copy

from tests.conftest import assert_error

SETUP = {
    "league": {
        "league_id": "lg-r1",
        "tenant_id": "tenant-alpha",
        "sport_id": "football",
        "transfer_window": {"open": "2026-09-01", "close": "2026-09-30"},
        "max_squad_size": 3,
        "required_positions": {"gk": 1},
    },
    "squads": [
        {"squad_id": "sq-a", "club_id": "club-a", "tenant_id": "tenant-alpha", "name": "A"},
        {"squad_id": "sq-b", "club_id": "club-b", "tenant_id": "tenant-alpha", "name": "B"},
        {"squad_id": "sq-x", "club_id": "club-x", "tenant_id": "tenant-beta", "name": "X"},
    ],
    "players": [
        {"player_id": "p1", "name": "Ali", "position": "gk", "squad_id": "sq-a", "role": "captain"},
        {"player_id": "p2", "name": "Bilal", "position": "df", "squad_id": "sq-a", "role": "starter"},
        {"player_id": "p3", "name": "Cheema", "position": "gk", "squad_id": "sq-b", "role": "starter"},
    ],
    "matches_in_progress": [],
}


def transfer_body(**overrides):
    body = {
        "request_id": "tr-001",
        "league_id": "lg-r1",
        "player_id": "p2",
        "type": "transfer",
        "from_squad_id": "sq-a",
        "to_squad_id": "sq-b",
        "effective_date": "2026-09-15",
        "loan_end_date": None,
        "reason": "Tactical move",
        "requested_by": "user-77",
    }
    body.update(overrides)
    return body


def do_setup(client, **league_overrides):
    body = copy.deepcopy(SETUP)
    body["league"].update(league_overrides)
    r = client.post("/audit/v1/roster/setup", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_setup_response(client, reset):
    assert do_setup(client) == {
        "league_id": "lg-r1",
        "status": "configured",
        "squad_counts": {"sq-a": 2, "sq-b": 1, "sq-x": 0},
    }
    # re-send replaces state
    assert client.post("/audit/v1/roster/transfer", json=transfer_body()).status_code == 201
    assert do_setup(client)["squad_counts"]["sq-b"] == 1
    hist = client.get("/audit/v1/roster/history/p2", params={"as_of": "2026-09-20"}).json()
    assert hist["history"] == [] and hist["current_squad_id"] == "sq-a"


def test_setup_validation_and_sport(client, reset):
    assert_error(client.post("/audit/v1/roster/setup", json={"squads": []}), 400, "VALIDATION_ERROR")
    body = copy.deepcopy(SETUP)
    body["league"]["sport_id"] = "nosuchsport"
    assert_error(client.post("/audit/v1/roster/setup", json=body), 404, "SPORT_NOT_FOUND")


def test_setup_defaults_from_sport(client, reset):
    body = copy.deepcopy(SETUP)
    del body["league"]["max_squad_size"]
    del body["league"]["required_positions"]
    assert client.post("/audit/v1/roster/setup", json=body).status_code == 201
    # football default requires 1 gk: moving the only gk of sq-a violates it
    r = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(player_id="p1"),
    )
    assert_error(r, 409, "MIN_POSITION_VIOLATION")


def test_transfer_success_and_replay(client, reset):
    do_setup(client)
    r = client.post("/audit/v1/roster/transfer", json=transfer_body())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["request_id"] == "tr-001"
    assert body["status"] == "accepted"
    assert body["state"] == "active"
    assert body["blocking_match_id"] is None
    assert body["registration"] == {
        "player_id": "p2",
        "league_id": "lg-r1",
        "squad_id": "sq-b",
        "parent_squad_id": None,
        "registration_type": "transfer",
        "start_date": "2026-09-15",
        "loan_end_date": None,
        "role": "substitute",
    }
    entry = body["audit_entry"]
    assert entry["audit_id"] == "au-0001"
    assert entry["action"] == "transfer"
    assert entry["from_squad_id"] == "sq-a" and entry["to_squad_id"] == "sq-b"
    assert entry["who"] == "user-77" and entry["why"] == "Tactical move"
    assert entry["state"] == "active" and entry["effective_date"] == "2026-09-15"
    assert len(entry["when"]) == 20 and entry["when"].endswith("Z")

    replay = client.post("/audit/v1/roster/transfer", json=transfer_body())
    assert replay.status_code == 200
    assert replay.json() == body
    other = client.post("/audit/v1/roster/transfer", json=transfer_body(reason="other"))
    assert_error(other, 400, "VALIDATION_ERROR")

    hist = client.get("/audit/v1/roster/history/p2", params={"as_of": "2026-09-20"}).json()
    assert hist["current_squad_id"] == "sq-b"
    assert len(hist["history"]) == 1


def test_rule1_validation(client, reset):
    do_setup(client)
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(effective_date="2026-13-01")), 400, "VALIDATION_ERROR")
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(type="loan", loan_end_date="2026-09-15")), 400, "VALIDATION_ERROR")
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(to_squad_id=None)), 400, "VALIDATION_ERROR")
    # validation beats unknown league
    err = assert_error(
        client.post("/audit/v1/roster/transfer", json=transfer_body(league_id="nope", type="bogus")),
        400,
        "VALIDATION_ERROR",
    )
    assert err["details"]["fields"] == ["type"]


def test_rule2_not_found(client, reset):
    do_setup(client)
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(league_id="nope")), 404, "LEAGUE_NOT_FOUND")
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(player_id="nobody")), 404, "PLAYER_NOT_FOUND")
    assert_error(client.post("/audit/v1/roster/transfer", json=transfer_body(to_squad_id="sq-zz")), 404, "SQUAD_NOT_FOUND")
    # 404 beats cross-tenant
    assert_error(
        client.post("/audit/v1/roster/transfer", json=transfer_body(player_id="nobody", to_squad_id="sq-x")),
        404,
        "PLAYER_NOT_FOUND",
    )


def test_rule3_cross_tenant_beats_not_in_squad(client, reset):
    do_setup(client)
    r = client.post("/audit/v1/roster/transfer", json=transfer_body(from_squad_id="sq-b", to_squad_id="sq-x"))
    assert_error(r, 409, "CROSS_TENANT_TRANSFER")


def test_rule4_not_in_squad_beats_window(client, reset):
    do_setup(client)
    r = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(from_squad_id="sq-b", to_squad_id="sq-a", effective_date="2026-12-01"),
    )
    assert_error(r, 409, "NOT_IN_SQUAD")


def test_rule5_window_beats_squad_full(client, reset):
    do_setup(client, max_squad_size=1)
    r = client.post("/audit/v1/roster/transfer", json=transfer_body(effective_date="2026-10-01"))
    assert_error(r, 409, "TRANSFER_WINDOW_CLOSED")
    # window is inclusive at both ends
    ok = client.post("/audit/v1/roster/transfer", json=transfer_body(effective_date="2026-09-01", to_squad_id="sq-b"))
    assert_error(ok, 409, "SQUAD_FULL")
    # release ignores the window
    rel = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="rel-1", type="release", to_squad_id=None, effective_date="2027-03-01"),
    )
    assert rel.status_code == 201, rel.text
    assert rel.json()["registration"] is None
    assert rel.json()["audit_entry"]["action"] == "release"
    assert rel.json()["audit_entry"]["to_squad_id"] is None
    hist = client.get("/audit/v1/roster/history/p2", params={"as_of": "2027-03-02"}).json()
    assert hist["current_squad_id"] is None


def test_rule6_on_loan_beats_squad_full(client, reset):
    do_setup(client)
    loan = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="ln-1", type="loan", loan_end_date="2026-12-31"),
    )
    assert loan.status_code == 201, loan.text
    reg = loan.json()["registration"]
    assert reg["registration_type"] == "loan"
    assert reg["parent_squad_id"] == "sq-a"
    assert reg["squad_id"] == "sq-b"
    assert reg["loan_end_date"] == "2026-12-31"
    # borrower now has 2, lender 1 (p2 counts toward borrower)
    # sq-b is not full (max 3) but even when it would be, PLAYER_ON_LOAN comes first
    for from_squad in ("sq-b", "sq-a"):
        r = client.post(
            "/audit/v1/roster/transfer",
            json=transfer_body(request_id="tr-2", from_squad_id=from_squad, to_squad_id="sq-a" if from_squad == "sq-b" else "sq-b", effective_date="2026-09-20"),
        )
        assert_error(r, 409, "PLAYER_ON_LOAN")


def test_rule7_squad_full_beats_min_position(client, reset):
    do_setup(client, max_squad_size=1)
    # p1 is the only gk of sq-a (rule 8 would fail) and sq-b is full (rule 7)
    r = client.post("/audit/v1/roster/transfer", json=transfer_body(player_id="p1"))
    assert_error(r, 409, "SQUAD_FULL")


def test_rule8_min_position(client, reset):
    do_setup(client)
    r = client.post("/audit/v1/roster/transfer", json=transfer_body(player_id="p1"))
    assert_error(r, 409, "MIN_POSITION_VIOLATION")
    # release also respects the minimum
    r = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(player_id="p1", type="release", to_squad_id=None),
    )
    assert_error(r, 409, "MIN_POSITION_VIOLATION")


def test_squad_full_counts_loans_toward_borrower(client, reset):
    do_setup(client, max_squad_size=2)
    loan = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="ln-1", type="loan", loan_end_date="2026-09-25"),
    )
    assert loan.status_code == 201
    # sq-b now has p3 + loaned p2 = 2 -> full
    body = copy.deepcopy(SETUP["players"])  # noqa: F841
    r = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="tr-9", player_id="p1", effective_date="2026-09-16"),
    )
    assert_error(r, 409, "SQUAD_FULL")


def test_last_window_day_in_progress_match_is_deferred(client, reset):
    body = copy.deepcopy(SETUP)
    body["matches_in_progress"] = [{"match_id": "m-live", "home_squad_id": "sq-a", "away_squad_id": "sq-b"}]
    assert client.post("/audit/v1/roster/setup", json=body).status_code == 201
    r = client.post("/audit/v1/roster/transfer", json=transfer_body(effective_date="2026-09-30"))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["state"] == "deferred_until_match_end"
    assert data["blocking_match_id"] == "m-live"
    assert data["audit_entry"]["state"] == "deferred_until_match_end"


def test_history_loan_return_written_once(client, reset):
    do_setup(client)
    loan = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="ln-1", type="loan", effective_date="2026-09-10", loan_end_date="2026-12-31"),
    )
    assert loan.status_code == 201
    during = client.get("/audit/v1/roster/history/p2", params={"as_of": "2026-12-31"}).json()
    assert during["current_squad_id"] == "sq-b"
    assert during["parent_squad_id"] == "sq-a"
    assert len(during["history"]) == 1

    for _ in range(3):
        r = client.get("/audit/v1/roster/history/p2", params={"as_of": "2027-01-05"})
        assert r.status_code == 200
        data = r.json()
        assert data["player_id"] == "p2"
        assert data["as_of"] == "2027-01-05"
        assert data["league_id"] == "lg-r1"
        assert data["current_squad_id"] == "sq-a"
        assert data["parent_squad_id"] is None
        actions = [e["action"] for e in data["history"]]
        assert actions == ["loan", "loan_return"]
        ret = data["history"][1]
        assert ret["who"] == "system"
        assert ret["effective_date"] == "2027-01-01"
        assert ret["from_squad_id"] == "sq-b" and ret["to_squad_id"] == "sq-a"
        assert ret["audit_id"] == "au-0002"


def test_history_errors(client, reset):
    do_setup(client)
    assert_error(client.get("/audit/v1/roster/history/nobody"), 404, "PLAYER_NOT_FOUND")
    assert_error(client.get("/audit/v1/roster/history/p1", params={"as_of": "2026-02-30"}), 400, "VALIDATION_ERROR")
    r = client.get("/audit/v1/roster/history/p1")
    assert r.status_code == 200
    assert r.json()["current_squad_id"] == "sq-a"


def test_transfer_after_loan_end_auto_returns(client, reset):
    do_setup(client, transfer_window={"open": "2026-09-01", "close": "2026-12-31"})
    loan = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="ln-1", type="loan", effective_date="2026-09-10", loan_end_date="2026-09-20"),
    )
    assert loan.status_code == 201
    r = client.post(
        "/audit/v1/roster/transfer",
        json=transfer_body(request_id="tr-2", from_squad_id="sq-a", to_squad_id="sq-b", effective_date="2026-10-01"),
    )
    assert r.status_code == 201, r.text
    hist = client.get("/audit/v1/roster/history/p2", params={"as_of": "2026-10-02"}).json()
    assert [e["action"] for e in hist["history"]] == ["loan", "loan_return", "transfer"]
    assert hist["current_squad_id"] == "sq-b"


def test_demo_roster_seeded(client, reset):
    from backend.core.db import SessionLocal
    from backend.modules.roster.service import destination_squads, roster_for_club

    with SessionLocal() as session:
        league_id, squad_id, players = roster_for_club(session, "club-alpha-1")
        assert league_id == "demo-roster-league" and squad_id == "demo-sq-alpha-1"
        assert len(players) == 8
        assert players[0]["role"] == "captain"
        dest = destination_squads(session, "club-alpha-1")
        assert dest == [{"squad_id": "demo-sq-alpha-2", "club_id": "club-alpha-2", "name": "Alpha Rovers"}]
