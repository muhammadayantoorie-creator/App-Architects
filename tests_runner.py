"""Disposable HTTP contract runner for SPEC.md. Run with: py -3 tests_runner.py."""

import base64
import hashlib
import hmac
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import requests

BASE = "http://localhost:8080"
SALT = "test"
M = "var-jersey-001-M"
L = "var-jersey-001-L"
SESSION = requests.Session()
FIVE_XX = []
RESULTS = []


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(key, identifier, payload):
    return hmac.new(key.encode(), (identifier + "|" + canonical(payload)).encode(), hashlib.sha256).hexdigest()


def body(response):
    try:
        return response.json()
    except ValueError:
        return response.text[:150]


def short(response):
    if response is None:
        return "no response"
    data = body(response)
    if isinstance(data, dict) and "error" in data:
        data = data["error"]
    elif isinstance(data, dict) and "access_token" in data:
        data = {**data, "access_token": "<redacted>"}
    elif isinstance(data, dict) and "receipt" in data:
        data = {key: value for key, value in data.items() if key != "receipt"}
    return f"{response.status_code} {str(data)[:130]}"


def call(method, path, **kwargs):
    response = SESSION.request(method, BASE + path, timeout=30, **kwargs)
    if response.status_code >= 500:
        FIVE_XX.append(f"{method} {path}: {short(response)}")
    return response


def error(response, status, code):
    data = body(response)
    return response.status_code == status and isinstance(data, dict) and isinstance(data.get("error"), dict) and data["error"].get("code") == code and all(key in data["error"] for key in ("code", "message", "details")) and isinstance(data["error"]["details"], dict)


def check(number, title, passed, actual, expected):
    RESULTS.append(bool(passed))
    state = "PASS" if passed else "FAIL"
    print(f"{number:02} {state} {title} | actual {actual} | expected {expected}", flush=True)


def reset(payload=None):
    return call("POST", "/audit/v1/reset", json={} if payload is None else payload)


def checkout(order_id, variant=M, token="tok_success", discount=None):
    return {"order_id": order_id, "customer_id": "cust-001", "items": [{"variant_id": variant, "quantity": 1}], "discount_code": discount, "payment": {"token": token}}


def event(event_id, typ, payload):
    return {"event_id": event_id, "match_id": "m1", "type": typ, "payload": payload}


def main():
    health = call("GET", "/health")
    check(1, "health", health.status_code == 200 and body(health) == {"status": "ok"}, short(health), '200 {status:ok}')

    r = reset()
    expected_reset = {"status": "reset_complete", "seed": 42, "sports": ["football", "basketball", "cricket", "esports"], "tenants": ["tenant-alpha", "tenant-beta"], "stock": {M: 1, L: 5}}
    check(2, "reset seed", r.status_code == 200 and body(r) == expected_reset, short(r), "200 baseline exact")

    r1, r2 = reset(), reset()
    check(3, "reset repeatability", r1.status_code == r2.status_code == 200 and body(r1) == body(r2) == expected_reset, f"{short(r1)} / {short(r2)}", "identical 200 baseline")

    r = call("POST", "/audit/v1/sports", json={"sport_id": "x'; DROP TABLE sports;--"})
    check(4, "sport injection validation", error(r, 400, "VALIDATION_ERROR"), short(r), "400 VALIDATION_ERROR envelope")

    r = call("POST", "/audit/v1/sports", data=b"x" * (2 * 1024 * 1024), headers={"Content-Type": "application/json"})
    check(5, "body limit", error(r, 413, "PAYLOAD_TOO_LARGE"), short(r), "413 PAYLOAD_TOO_LARGE")

    logins = [call("POST", "/api/v1/auth/login", json={"email": f"{role}@nascon.test", "password": "Nascon@26"}) for role in ("manager", "admin", "organizer", "player", "viewer")]
    ok = all(x.status_code == 200 and isinstance(body(x), dict) and isinstance(body(x).get("access_token"), str) for x in logins)
    check(6, "five demo logins", ok, ", ".join(short(x) for x in logins), "five 200 access_token")

    matrix = call("POST", "/audit/v1/rbac-matrix", json={})
    md = body(matrix) if isinstance(body(matrix), dict) else {}
    tokens = md.get("tokens", {})
    context = md.get("context", {})
    expected_context = {"tenant_id": "tenant-alpha", "foreign_tenant_id": "tenant-beta", "own_league_id": "league-alpha-1", "other_league_id": "league-alpha-2", "foreign_league_id": "league-beta-1", "own_club_id": "club-alpha-1", "other_club_id": "club-alpha-2", "foreign_club_id": "club-beta-1", "own_player_id": "player-alpha-1", "other_player_id": "player-alpha-2", "foreign_player_id": "player-beta-1"}
    roles = ("super_admin", "league_organizer", "club_manager", "player", "viewer")
    check(7, "RBAC matrix context", matrix.status_code == 200 and set(tokens) == set(roles) and all(isinstance(x, str) for x in tokens.values()) and context == expected_context, f"{matrix.status_code} tokens={list(tokens)} context={context}", "200 five JWTs + exact context")

    probes = [
        ("P1", "POST", "/audit/v1/rbac/tenants", {"super_admin"}),
        ("P2-own", "POST", "/audit/v1/rbac/leagues/league-alpha-1/fixtures", {"super_admin", "league_organizer"}),
        ("P2-other", "POST", "/audit/v1/rbac/leagues/league-alpha-2/fixtures", {"super_admin"}),
        ("P2-foreign", "POST", "/audit/v1/rbac/leagues/league-beta-1/fixtures", {"super_admin"}),
        ("P3-own", "POST", "/audit/v1/rbac/clubs/club-alpha-1/roster", {"super_admin", "club_manager"}),
        ("P3-other", "POST", "/audit/v1/rbac/clubs/club-alpha-2/roster", {"super_admin"}),
        ("P3-foreign", "POST", "/audit/v1/rbac/clubs/club-beta-1/roster", {"super_admin"}),
        ("P4-own", "POST", "/audit/v1/rbac/clubs/club-alpha-1/products", {"super_admin", "club_manager"}),
        ("P4-other", "POST", "/audit/v1/rbac/clubs/club-alpha-2/products", {"super_admin"}),
        ("P4-foreign", "POST", "/audit/v1/rbac/clubs/club-beta-1/products", {"super_admin"}),
        ("P5-own", "PATCH", "/audit/v1/rbac/players/player-alpha-1", {"super_admin", "club_manager", "player"}),
        ("P5-other", "PATCH", "/audit/v1/rbac/players/player-alpha-2", {"super_admin"}),
        ("P5-foreign", "PATCH", "/audit/v1/rbac/players/player-beta-1", {"super_admin"}),
        ("P6-own", "GET", "/audit/v1/rbac/clubs/club-alpha-1", set(roles)),
        ("P6-other", "GET", "/audit/v1/rbac/clubs/club-alpha-2", set(roles)),
        ("P6-foreign", "GET", "/audit/v1/rbac/clubs/club-beta-1", {"super_admin"}),
        ("P7", "GET", "/audit/v1/rbac/platform/config", {"super_admin"}),
    ]
    mismatches = []
    for name, method, path, allowed in probes:
        for role in roles:
            token = tokens.get(role, "")
            r = call(method, path, headers={"Authorization": f"Bearer {token}"}, **({"json": {}} if method != "GET" else {}))
            good = r.status_code == 200 and body(r) == {"authorized": True} if role in allowed else error(r, 403, "FORBIDDEN")
            if not good:
                mismatches.append(f"{name}/{role}: {short(r)} expected {'200 authorized' if role in allowed else '403 FORBIDDEN'}")
    check(8, "RBAC 85 matrix cells", not mismatches, f"{85-len(mismatches)}/85; mismatches={mismatches}", "85/85 exact")

    good_token = tokens.get("super_admin", "")
    parts = good_token.split(".")
    tampered = ".".join(parts[:2] + [("A" if parts[2][:1] != "A" else "B") + parts[2][1:]]) if len(parts) == 3 and parts[2] else "bad.token"
    alg_none = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode() + "." + (parts[1] if len(parts) > 1 else "e30") + "."
    sec = [call("GET", "/audit/v1/rbac/platform/config", headers=h) for h in ({}, {"Authorization": f"Bearer {tampered}"}, {"Authorization": f"Bearer {alg_none}"})]
    check(9, "JWT rejection", all(error(x, 401, "UNAUTHENTICATED") for x in sec), ", ".join(short(x) for x in sec), "three 401 UNAUTHENTICATED")

    ip_header = {"X-Forwarded-For": "198.51.100.73"}
    start = time.monotonic()
    pings = [call("GET", "/api/v1/ping", headers=ip_header) for _ in range(150)]
    elapsed = time.monotonic() - start
    limited = [x for x in pings if error(x, 429, "RATE_LIMITED") and x.headers.get("Retry-After")]
    healths = [call("GET", "/health", headers=ip_header) for _ in range(300)]
    time.sleep(11)
    after = call("GET", "/api/v1/ping", headers=ip_header)
    ping_ok = pings[0].status_code == 200 and body(pings[0]) == {"pong": True} and elapsed < 5 and len(limited) >= 40 and all(x.status_code == 200 for x in healths) and after.status_code == 200 and body(after) == {"pong": True}
    check(10, "rate limit + health exemption", ping_ok, f"first={short(pings[0])}, 429={len(limited)}, elapsed={elapsed:.2f}s, health200={sum(x.status_code==200 for x in healths)}/300, after={short(after)}", "first 200, >=40 429 <5s, health 300x200, after 200")

    reset()
    barrier = Barrier(20)
    orders = [checkout(f"ord-concurrent-{i:02d}") for i in range(20)]
    def buy(order):
        barrier.wait(timeout=15)
        return call("POST", "/audit/v1/checkout", json=order)
    with ThreadPoolExecutor(max_workers=20) as pool:
        burst = list(pool.map(buy, orders))
    winners = [(order, response) for order, response in zip(orders, burst) if response.status_code == 201]
    out = [x for x in burst if error(x, 409, "OUT_OF_STOCK")]
    inv = call("GET", f"/audit/v1/inventory/{M}")
    check(11, "20 concurrent checkouts", len(winners) == 1 and len(out) == 19 and inv.status_code == 200 and body(inv) == {"variant_id": M, "stock": 0, "reserved": 0}, f"201={len(winners)}, 409 OUT_OF_STOCK={len(out)}, inventory={short(inv)}", "1/19; stock 0 reserved 0")

    winner_order, winner_response = winners[0] if winners else ({}, None)
    wd = body(winner_response) if winner_response is not None else {}
    receipt = wd.get("receipt", {}) if isinstance(wd, dict) else {}
    payload = receipt.get("payload", {})
    try:
        pdf = base64.b64decode(receipt.get("pdf_base64", ""), validate=True)
    except Exception:
        pdf = b""
    expected_fields = {"order_id", "status", "currency", "items", "subtotal_minor", "discount_minor", "total_minor", "payment", "receipt"}
    receipt_ok = bool(winners) and set(wd) == expected_fields and set(receipt) == {"payload", "signature", "pdf_base64"} and set(payload) == {"order_id", "customer_id", "items", "subtotal_minor", "discount_minor", "total_minor", "currency", "paid_at"} and wd.get("status") == "paid" and wd.get("currency") == "PKR" and wd.get("subtotal_minor") == 450000 and wd.get("total_minor") == 450000 and receipt.get("signature") == sign(SALT, wd.get("order_id", ""), payload) and pdf.startswith(b"%PDF") and wd.get("order_id", "").encode() in pdf and b"PKR 4500.00" in pdf
    check(12, "signed PDF receipt", receipt_ok, f"{short(winner_response)} signature={receipt.get('signature')} pdf={pdf[:8]!r} text={wd.get('order_id', '').encode() in pdf if isinstance(wd, dict) else False}/{b'PKR 4500.00' in pdf}", "exact fields, HMAC test, PDF text")

    replay = call("POST", "/audit/v1/checkout", json=winner_order) if winners else None
    changed = dict(winner_order, customer_id="different") if winners else {}
    conflict = call("POST", "/audit/v1/checkout", json=changed) if winners else None
    check(13, "checkout idempotency", replay is not None and replay.status_code == 200 and body(replay) == wd and error(conflict, 409, "DUPLICATE_ORDER_ID"), f"replay={short(replay)} conflict={short(conflict)}", "200 identical; 409 DUPLICATE_ORDER_ID")

    reset({"stock": {M: 1, L: 5}})
    decline = call("POST", "/audit/v1/checkout", json=checkout("ord-decline", L, "tok_declined"))
    inv1 = call("GET", f"/audit/v1/inventory/{L}")
    capture = call("POST", "/audit/v1/checkout", json=checkout("ord-capture-fail", L, "tok_capture_fail"))
    inv2 = call("GET", f"/audit/v1/inventory/{L}")
    check(14, "payment rollback", error(decline, 402, "PAYMENT_DECLINED") and error(capture, 402, "PAYMENT_CAPTURE_FAILED") and body(inv1) == body(inv2) == {"variant_id": L, "stock": 5, "reserved": 0}, f"decline={short(decline)} inv={short(inv1)} capture={short(capture)} inv={short(inv2)}", "two 402; L stock 5 reserved 0")

    bad = call("POST", "/audit/v1/checkout", json=checkout("ord-bad-discount", L, discount="BAD"))
    welcome = call("POST", "/audit/v1/checkout", json=checkout("ord-welcome", L, discount="WELCOME10"))
    wbody = body(welcome)
    check(15, "discount", error(bad, 400, "INVALID_DISCOUNT_CODE") and welcome.status_code == 201 and isinstance(wbody, dict) and wbody.get("discount_minor") == (wbody.get("subtotal_minor", 0) * 10 // 100), f"BAD={short(bad)} WELCOME10={short(welcome)}", "400 invalid; 201 floor(10%)")

    vector = sign("demo-salt", "evt-1", {"team_id": "t1", "event_type": "goal"})
    check(16, "Appendix A HMAC vector", vector == "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501", vector, "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501")

    rr = call("POST", "/audit/v1/fixtures", json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4", "t5"], "params": {"legs": 1}})
    rrd = body(rr)
    rounds = rrd.get("rounds", []) if isinstance(rrd, dict) else []
    rr_ok = rr.status_code == 200 and len(rounds) == 5 and all(len(round_.get("matches", [])) == 2 and len(round_.get("byes", [])) == 1 and all(match.get("match_id") == f"RR-L1-R{round_['round']}-M{i}" for i, match in enumerate(round_.get("matches", []), 1)) for round_ in rounds)
    check(17, "round robin fixtures", rr_ok, f"{rr.status_code} rounds={len(rounds)} matches={[len(x.get('matches',[])) for x in rounds]} byes={[x.get('byes') for x in rounds]}", "200; 5 rounds, 2 matches + 1 bye each, exact IDs")

    se = call("POST", "/audit/v1/fixtures", json={"format": "single_elim", "teams": ["t1", "t2", "t3", "t4", "t5", "t6"], "params": {}})
    sed = body(se)
    srounds = sed.get("rounds", []) if isinstance(sed, dict) else []
    first = srounds[0].get("matches", []) if srounds else []
    second = srounds[1].get("matches", []) if len(srounds) > 1 else []
    se_ok = se.status_code == 200 and sed.get("bracket_size") == 8 and first and first[0].get("match_id") == "R1M1" and first[0].get("bye") is True and first[0].get("home") == "t1" and second and second[0].get("match_id") == "R2M1" and second[0].get("home") == "t1"
    check(18, "single elimination bye", se_ok, f"{se.status_code} size={sed.get('bracket_size')} R1M1={first[0] if first else None} R2M1={second[0] if second else None}", "200 size 8, R1M1 bye t1, R2M1.home t1")

    reset()
    league = call("POST", "/audit/v1/leagues", json={"league_id": "lg-1", "sport_id": "football", "teams": ["t1", "t2", "t3", "t4"], "fixtures": [{"match_id": "m1", "home": "t1", "away": "t2"}], "qualification": {"spots": 2}})
    start_ev = call("POST", "/audit/v1/events", json=event("evt-1", "match_start", {}))
    goal = event("evt-2", "score", {"team_id": "t1", "event_type": "goal"})
    goal_ev = call("POST", "/audit/v1/events", json=goal)
    end_ev = call("POST", "/audit/v1/events", json=event("evt-3", "match_end", {}))
    score = call("GET", "/audit/v1/score/m1")
    replay_ev = call("POST", "/audit/v1/events", json=goal)
    gd, sd = body(goal_ev), body(score)
    event_ok = league.status_code == 201 and all(x.status_code == 201 for x in (start_ev, goal_ev, end_ev)) and isinstance(gd, dict) and gd.get("signature") == sign(SALT, "evt-2", goal["payload"]) and score.status_code == 200 and isinstance(sd, dict) and sd.get("status") == "completed" and sd.get("outcome") == "home_win" and sd.get("home", {}).get("score") == 1 and replay_ev.status_code == 200 and body(replay_ev) == gd
    check(19, "league event score + replay", event_ok, f"league={short(league)} events={[short(x) for x in (start_ev,goal_ev,end_ev)]} score={short(score)} replay={short(replay_ev)}", "201 league/events; signed goal; 200 completed home_win 1; 200 identical replay")

    comp = call("POST", "/audit/v1/events", json=event("evt-4", "compensation", {"compensates": "evt-2", "reason": "correction"}))
    score2 = call("GET", "/audit/v1/score/m1")
    sd2 = body(score2)
    target = next((x for x in sd2.get("events", []) if x.get("event_id") == "evt-2"), {}) if isinstance(sd2, dict) else {}
    check(20, "compensation projects draw", comp.status_code == 201 and score2.status_code == 200 and sd2.get("outcome") == "draw" and target.get("compensated") is True and sd2.get("home", {}).get("score") == 0, f"comp={short(comp)} score={short(score2)} target={target}", "201; completed draw, goal compensated, home 0")

    standings = call("GET", "/audit/v1/standings/lg-1")
    st = body(standings)
    teams = ["t1", "t2", "t3", "t4"]
    h2h = st.get("h2h", {}) if isinstance(st, dict) else {}
    st_ok = standings.status_code == 200 and len(st.get("table", [])) == 4 and {x.get("team_id") for x in st.get("table", [])} == set(teams) and all(isinstance(h2h.get(a, {}).get(b), dict) for a in teams for b in teams if a != b)
    check(21, "standings and H2H", st_ok, f"{standings.status_code} rows={len(st.get('table',[])) if isinstance(st,dict) else 0} h2h={sum(isinstance(h2h.get(a,{}).get(b),dict) for a in teams for b in teams if a!=b)}/12", "200 four teams, 12 ordered H2H pairs")

    kabaddi = {"sport_id": "kabaddi", "name": "Kabaddi", "scoring_model": "event", "periods": {"count": 2, "duration_minutes": 20}, "scoring_events": {"raid_point": {"points": 1}, "tackle_point": {"points": 1}, "all_out": {"points": 2}}, "draw_allowed": False, "overtime": {"policy": "golden_score", "duration_minutes": 5}, "tie_break_order": ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"], "roster": {"min_squad_size": 7, "max_squad_size": 12, "required_positions": {"raider": 2, "defender": 3}}}
    sport1 = call("POST", "/audit/v1/sports", json=kabaddi)
    sport2 = call("POST", "/audit/v1/sports", json=kabaddi)
    check(22, "mystery sport duplicate", sport1.status_code == 201 and error(sport2, 409, "SPORT_EXISTS"), f"create={short(sport1)} repeat={short(sport2)}", "201 created; 409 SPORT_EXISTS")

    roster = {"league": {"league_id": "lg-r1", "tenant_id": "tenant-alpha", "sport_id": "football", "transfer_window": {"open": "2026-09-01", "close": "2026-09-30"}, "max_squad_size": 3, "required_positions": {"gk": 1}}, "squads": [{"squad_id": "sq-a", "club_id": "club-a", "tenant_id": "tenant-alpha", "name": "A"}, {"squad_id": "sq-b", "club_id": "club-b", "tenant_id": "tenant-alpha", "name": "B"}], "players": [{"player_id": "p1", "name": "Ali", "position": "gk", "squad_id": "sq-a", "role": "captain"}, {"player_id": "p2", "name": "Bilal", "position": "df", "squad_id": "sq-a", "role": "starter"}], "matches_in_progress": [{"match_id": "m-live", "home_squad_id": "sq-a", "away_squad_id": "sq-b"}]}
    setup = call("POST", "/audit/v1/roster/setup", json=roster)
    transfer_body = {"request_id": "tr-001", "league_id": "lg-r1", "player_id": "p2", "type": "transfer", "from_squad_id": "sq-a", "to_squad_id": "sq-b", "effective_date": "2026-09-30", "loan_end_date": None, "reason": "Tactical move", "requested_by": "user-77"}
    transfer = call("POST", "/audit/v1/roster/transfer", json=transfer_body)
    transfer_replay = call("POST", "/audit/v1/roster/transfer", json=transfer_body)
    history = call("GET", "/audit/v1/roster/history/p2", params={"as_of": "2026-10-01"})
    hd = body(history)
    roster_ok = setup.status_code == 201 and transfer.status_code == 201 and transfer_replay.status_code == 200 and body(transfer_replay) == body(transfer) and history.status_code == 200 and isinstance(hd, dict) and hd.get("player_id") == "p2" and len(hd.get("history", [])) >= 1
    check(23, "roster transfer + history", roster_ok, f"setup={short(setup)} transfer={short(transfer)} replay={short(transfer_replay)} history={short(history)}", "201 setup/transfer, 200 replay identical/history p2")

    sync_init = call("POST", "/audit/v1/events", json={"event_id": "evt-sync-init", "match_id": "m-sync", "type": "match_init", "payload": {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"}})
    sync_start = call("POST", "/audit/v1/events", json={"event_id": "evt-sync-start", "match_id": "m-sync", "type": "match_start", "payload": {}})
    sync_body = {"device_id": "dev-1", "actions": [{"action_id": "a1", "type": "score_event", "queued_at": "2026-10-17T11:00:00Z", "base_version": 2, "payload": {"event_id": "evt-sync-score", "match_id": "m-sync", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}}]}
    sync1 = call("POST", "/audit/v1/offline-sync", json=sync_body)
    sync2 = call("POST", "/audit/v1/offline-sync", json=sync_body)
    d1, d2 = body(sync1), body(sync2)
    results2 = d2.get("results", []) if isinstance(d2, dict) else []
    sync_ok = sync_init.status_code == sync_start.status_code == 201 and sync1.status_code == sync2.status_code == 200 and isinstance(d1, dict) and len(d1.get("results", [])) == 1 and d1["results"][0].get("status") == "applied" and len(results2) == 1 and all(x.get("status") == "duplicate" and x.get("resolution") == "skipped_duplicate" for x in results2)
    check(24, "offline sync replay", sync_ok, f"init={short(sync_init)} start={short(sync_start)} first={short(sync1)} replay={short(sync2)}", "201 init/start, 200 applied then 200 duplicate")

    print(f"TOTAL {sum(RESULTS)}/{len(RESULTS)} PASS; 5xx={len(FIVE_XX)} {FIVE_XX}", flush=True)


if __name__ == "__main__":
    main()
