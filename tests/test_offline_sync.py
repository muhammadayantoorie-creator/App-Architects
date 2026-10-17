import copy

from tests.conftest import assert_error
from tests.test_roster import SETUP, transfer_body

URL = "/audit/v1/offline-sync"


def init_match(client, reset, match_id, start=True):
    sport_id = reset["sports"][0]
    r = client.post(
        "/audit/v1/events",
        json={
            "event_id": f"{match_id}-init",
            "match_id": match_id,
            "type": "match_init",
            "payload": {"sport_id": sport_id, "home_team_id": "t1", "away_team_id": "t2"},
        },
    )
    assert r.status_code == 201, r.text
    if start:
        r = client.post(
            "/audit/v1/events",
            json={"event_id": f"{match_id}-start", "match_id": match_id, "type": "match_start", "payload": {}},
        )
        assert r.status_code == 201, r.text


def score_action(action_id, match_id, event_id, base, queued_at="2026-10-17T11:00:00Z", team="t1"):
    return {
        "action_id": action_id,
        "type": "score_event",
        "queued_at": queued_at,
        "base_version": base,
        "payload": {
            "event_id": event_id,
            "match_id": match_id,
            "type": "score",
            "payload": {"team_id": team, "event_type": "goal"},
        },
    }


def roster_action(action_id, base, queued_at="2026-10-17T11:05:00Z", **overrides):
    return {
        "action_id": action_id,
        "type": "roster_transfer",
        "queued_at": queued_at,
        "base_version": base,
        "payload": transfer_body(**overrides),
    }


def test_applied_rebased_and_duplicate_resend(client, reset):
    init_match(client, reset, "m-os1")  # version 2
    body = {
        "device_id": "dev-1",
        "actions": [
            score_action("a1", "m-os1", "evt-os-1", 2, "2026-10-17T11:00:00Z"),
            score_action("a2", "m-os1", "evt-os-2", 2, "2026-10-17T11:01:00Z"),
        ],
    }
    r = client.post(URL, json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["device_id"] == "dev-1"
    a1, a2 = data["results"]
    assert a1["action_id"] == "a1"
    assert (a1["status"], a1["resolution"], a1["error_code"]) == ("applied", "appended", None)
    assert a1["processed_order"] == 1 and a1["server_version"] == 3
    assert isinstance(a1["signature"], str) and len(a1["signature"]) == 64
    assert (a2["status"], a2["resolution"]) == ("applied", "rebased_append")
    assert a2["server_version"] == 4 and a2["processed_order"] == 2
    assert data["summary"] == {"applied": 2, "rejected": 0, "duplicate": 0}

    again = client.post(URL, json=body).json()
    for res in again["results"]:
        assert (res["status"], res["resolution"], res["error_code"]) == ("duplicate", "skipped_duplicate", None)
        assert res["server_version"] == 4
        assert res["signature"] is None
    assert again["summary"] == {"applied": 0, "rejected": 0, "duplicate": 2}
    assert client.get("/audit/v1/score/m-os1").json()["version"] == 4

    # Same event from another device: identical payload -> duplicate
    other = client.post(
        URL, json={"device_id": "dev-2", "actions": [score_action("b1", "m-os1", "evt-os-1", 4)]}
    ).json()
    assert other["results"][0]["status"] == "duplicate"


def test_rejections(client, reset):
    init_match(client, reset, "m-up", start=False)  # version 1, upcoming
    init_match(client, reset, "m-live")  # version 2
    body = {
        "device_id": "dev-3",
        "actions": [
            score_action("r1", "m-up", "evt-r1", 1, "2026-10-17T11:00:00Z"),
            score_action("r2", "m-live", "evt-r2", 9, "2026-10-17T11:01:00Z"),
            score_action("r3", "m-missing", "evt-r3", 0, "2026-10-17T11:02:00Z"),
            score_action("r4", "m-live", "evt-r4", 2, "2026-10-17T11:03:00Z"),
        ],
    }
    data = client.post(URL, json=body).json()
    r1, r2, r3, r4 = data["results"]
    assert (r1["status"], r1["resolution"], r1["error_code"]) == ("rejected", "server_wins", "MATCH_NOT_IN_PROGRESS")
    assert r1["server_version"] == 1 and r1["signature"] is None
    assert (r2["status"], r2["error_code"], r2["server_version"]) == ("rejected", "INVALID_BASE_VERSION", 2)
    assert (r3["status"], r3["error_code"]) == ("rejected", "MATCH_NOT_FOUND")
    assert (r4["status"], r4["resolution"], r4["server_version"]) == ("applied", "appended", 3)
    assert data["summary"] == {"applied": 1, "rejected": 3, "duplicate": 0}

    # Event id reused with a different body -> rule rejects
    dup = score_action("r5", "m-live", "evt-r4", 3, team="t2")
    res = client.post(URL, json={"device_id": "dev-3", "actions": [dup]}).json()["results"][0]
    assert (res["status"], res["error_code"]) == ("rejected", "DUPLICATE_EVENT_ID")


def test_roster_actions(client, reset):
    setup = copy.deepcopy(SETUP)
    setup["league"]["max_squad_size"] = 2
    assert client.post("/audit/v1/roster/setup", json=setup).status_code == 201
    body = {
        "device_id": "dev-4",
        "actions": [
            # sq-b has 1 player; p2 joins (2), then p1 cannot (full)
            roster_action("t1", 0, "2026-10-17T11:00:00Z", request_id="o-1"),
            roster_action("t2", 0, "2026-10-17T11:01:00Z", request_id="o-2", player_id="p1"),
            roster_action("t3", 0, "2026-10-17T11:02:00Z", request_id="o-3", player_id="ghost"),
            roster_action("t4", 5, "2026-10-17T11:03:00Z", request_id="o-4", from_squad_id="sq-b", to_squad_id="sq-a"),
        ],
    }
    data = client.post(URL, json=body).json()
    t1, t2, t3, t4 = data["results"]
    assert (t1["status"], t1["resolution"], t1["server_version"], t1["signature"]) == ("applied", "appended", 1, None)
    assert (t2["status"], t2["resolution"], t2["error_code"], t2["server_version"]) == (
        "rejected",
        "server_wins",
        "SQUAD_FULL",
        0,
    )
    assert (t3["status"], t3["error_code"]) == ("rejected", "PLAYER_NOT_FOUND")
    assert (t4["status"], t4["error_code"], t4["server_version"]) == ("rejected", "INVALID_BASE_VERSION", 1)

    # stale base version on a valid move -> rebased_append
    back = roster_action("t5", 0, request_id="o-5", from_squad_id="sq-b", to_squad_id="sq-a", effective_date="2026-09-20")
    res = client.post(URL, json={"device_id": "dev-4", "actions": [back]}).json()["results"][0]
    assert (res["status"], res["resolution"], res["server_version"]) == ("applied", "rebased_append", 2)

    # same request_id from another device -> duplicate
    res = client.post(URL, json={"device_id": "dev-5", "actions": [back]}).json()["results"][0]
    assert (res["status"], res["resolution"], res["server_version"]) == ("duplicate", "skipped_duplicate", 2)


def test_processing_order_by_queued_at(client, reset):
    init_match(client, reset, "m-ord")  # version 2
    body = {
        "device_id": "dev-6",
        "actions": [
            score_action("late", "m-ord", "evt-late", 2, "2026-10-17T12:00:00Z"),
            score_action("early", "m-ord", "evt-early", 2, "2026-10-17T10:00:00Z"),
            score_action("tie-a", "m-ord", "evt-tie-a", 2, "2026-10-17T11:00:00Z"),
            score_action("tie-b", "m-ord", "evt-tie-b", 2, "2026-10-17T11:00:00Z"),
        ],
    }
    data = client.post(URL, json=body).json()
    ids = [r["action_id"] for r in data["results"]]
    assert ids == ["late", "early", "tie-a", "tie-b"]
    orders = {r["action_id"]: r["processed_order"] for r in data["results"]}
    assert orders == {"early": 1, "tie-a": 2, "tie-b": 3, "late": 4}
    versions = {r["action_id"]: r["server_version"] for r in data["results"]}
    assert versions == {"early": 3, "tie-a": 4, "tie-b": 5, "late": 6}
    assert data["results"][1]["resolution"] == "appended"
    assert data["results"][0]["resolution"] == "rebased_append"


def test_envelope_validation(client, reset):
    assert_error(client.post(URL, json={"device_id": "dev-1", "actions": []}), 400, "VALIDATION_ERROR")
    many = [score_action(f"x{i}", "m", f"e{i}", 0) for i in range(101)]
    assert_error(client.post(URL, json={"device_id": "dev-1", "actions": many}), 400, "VALIDATION_ERROR")
    bad = score_action("a1", "m", "e1", 0)
    bad["queued_at"] = "2026-10-17 11:00:00"
    err = assert_error(client.post(URL, json={"device_id": "dev-1", "actions": [bad]}), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["actions.0.queued_at"]
    bad = score_action("a1", "m", "e1", -1)
    bad["type"] = "other"
    err = assert_error(client.post(URL, json={"device_id": "bad|id", "actions": [bad]}), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["actions.0.base_version", "actions.0.type", "device_id"]
