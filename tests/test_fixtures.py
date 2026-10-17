"""POST /audit/v1/fixtures — round robin, swiss, single and double elimination."""

from __future__ import annotations

import itertools
from collections import Counter

import pytest

from tests.conftest import assert_error

URL = "/audit/v1/fixtures"


def teams(n: int) -> list[str]:
    return [f"t{i}" for i in range(1, n + 1)]


def post(client, body):
    return client.post(URL, json=body)


def ok(client, body) -> dict:
    r = post(client, body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- round robin


@pytest.mark.parametrize("legs", [1, 2])
@pytest.mark.parametrize("n", list(range(2, 13)))
def test_round_robin_properties(client, n, legs):
    body = ok(client, {"format": "round_robin", "teams": teams(n), "params": {"legs": legs}})
    per_leg = n - 1 if n % 2 == 0 else n
    assert body["format"] == "round_robin"
    assert body["legs"] == legs and body["team_count"] == n
    assert body["round_count"] == per_leg * legs
    assert [r["round"] for r in body["rounds"]] == list(range(1, per_leg * legs + 1))
    unordered: Counter = Counter()
    ordered: Counter = Counter()
    byes_per_leg: dict[int, Counter] = {1: Counter(), 2: Counter()}
    home_away = {leg: {t: [0, 0] for t in teams(n)} for leg in (1, 2)}
    for rnd in body["rounds"]:
        leg = 1 if rnd["round"] <= per_leg else 2
        assert len(rnd["matches"]) == n // 2
        seen = []
        for idx, m in enumerate(rnd["matches"], start=1):
            assert m["match_id"] == f"RR-L{leg}-R{rnd['round']}-M{idx}"
            assert m["leg"] == leg and m["status"] == "scheduled" and m["awarded_to"] is None
            assert m["home"] != m["away"]
            seen += [m["home"], m["away"]]
            unordered[frozenset((m["home"], m["away"]))] += 1
            ordered[(m["home"], m["away"])] += 1
            home_away[leg][m["home"]][0] += 1
            home_away[leg][m["away"]][1] += 1
        if n % 2 == 0:
            assert rnd["byes"] == []
        else:
            assert len(rnd["byes"]) == 1
            byes_per_leg[leg][rnd["byes"][0]] += 1
            seen += rnd["byes"]
        assert sorted(seen) == sorted(teams(n))
    assert len(unordered) == n * (n - 1) // 2
    assert all(c == legs for c in unordered.values())
    if legs == 2:
        assert len(ordered) == n * (n - 1) and all(c == 1 for c in ordered.values())
    for leg in range(1, legs + 1):
        for h, a in home_away[leg].values():
            assert abs(h - a) <= 1
        if n % 2:
            assert byes_per_leg[leg] == Counter({t: 1 for t in teams(n)})
    total = legs * n * (n - 1) // 2
    assert body["summary"] == {"total": total, "scheduled": total, "forfeit": 0, "voided": 0}


def test_round_robin_spec_example_forfeit(client):
    body = ok(
        client,
        {
            "format": "round_robin",
            "teams": teams(5),
            "params": {"legs": 1, "withdrawals": [{"team_id": "t3", "after_round": 2}], "withdrawal_policy": "forfeit_remaining"},
        },
    )
    assert body["round_count"] == 5
    assert body["rounds"][0]["matches"][0] == {
        "match_id": "RR-L1-R1-M1", "leg": 1, "home": "t2", "away": "t5", "status": "scheduled", "awarded_to": None,
    }
    assert body["rounds"][0]["byes"] == ["t1"]
    for rnd in body["rounds"]:
        for m in rnd["matches"]:
            if "t3" in (m["home"], m["away"]):
                if rnd["round"] > 2:
                    assert m["status"] == "forfeit"
                    assert m["awarded_to"] == (m["away"] if m["home"] == "t3" else m["home"])
                else:
                    assert m["status"] == "scheduled"
            else:
                assert m["status"] == "scheduled"
    s = body["summary"]
    assert s["total"] == 10 and s["forfeit"] + s["scheduled"] == 10 and s["voided"] == 0
    assert s == {"total": 10, "scheduled": 8, "forfeit": 2, "voided": 0}


@pytest.mark.parametrize("legs", [1, 2])
def test_round_robin_withdrawal_policies(client, legs):
    params = {"legs": legs, "withdrawals": [{"team_id": "t2", "after_round": 3}, {"team_id": "t4", "after_round": 0}]}
    fo = ok(client, {"format": "round_robin", "teams": teams(7), "params": dict(params)})
    vo = ok(client, {"format": "round_robin", "teams": teams(7), "params": dict(params, withdrawal_policy="void_all")})
    after = {"t2": 3, "t4": 0}
    for body, policy in ((fo, "forfeit_remaining"), (vo, "void_all")):
        counts = Counter()
        for rnd in body["rounds"]:
            assert len(rnd["byes"]) == 1  # byes unaffected
            for m in rnd["matches"]:
                h, a, r = m["home"], m["away"], rnd["round"]
                if policy == "void_all":
                    exp = ("voided", None) if (h in after or a in after) else ("scheduled", None)
                else:
                    ho = h in after and r > after[h]
                    ao = a in after and r > after[a]
                    if ho and ao:
                        exp = ("voided", None)
                    elif ho:
                        exp = ("forfeit", a)
                    elif ao:
                        exp = ("forfeit", h)
                    else:
                        exp = ("scheduled", None)
                assert (m["status"], m["awarded_to"]) == exp, (policy, m)
                counts[m["status"]] += 1
        s = body["summary"]
        assert s["total"] == legs * 21
        assert s == {"total": legs * 21, "scheduled": counts["scheduled"], "forfeit": counts["forfeit"], "voided": counts["voided"]}
    assert vo["summary"]["voided"] == legs * 11  # 6 + 6 - 1 fixtures per leg


@pytest.mark.parametrize(
    "body",
    [
        {"format": "round_robin", "teams": teams(4), "params": {"withdrawals": [{"team_id": "zz", "after_round": 1}]}},
        {"format": "round_robin", "teams": teams(4), "params": {"withdrawals": [{"team_id": "t1", "after_round": 4}]}},
        {"format": "round_robin", "teams": teams(4), "params": {"withdrawals": [{"team_id": "t1", "after_round": -1}]}},
        {"format": "round_robin", "teams": teams(4), "params": {"legs": 3}},
        {"format": "round_robin", "teams": teams(4), "params": {"withdrawal_policy": "nope"}},
        {"format": "round_robin", "teams": ["t1"]},
        {"format": "round_robin", "teams": teams(41)},
        {"format": "round_robin", "teams": ["t1", "t1", "t2"]},
        {"format": "round_robin", "teams": ["t1", "bad|id"]},
        {"format": "nope", "teams": teams(4)},
        {"teams": teams(4)},
        {"format": "swiss", "teams": teams(65)},
        {"format": "double_elim", "teams": teams(2)},
        {"format": "single_elim", "teams": teams(129)},
        {"format": "single_elim", "teams": teams(4), "params": []},
        [1, 2],
    ],
)
def test_validation_errors(client, body):
    err = assert_error(post(client, body), 400, "VALIDATION_ERROR")
    assert isinstance(err["details"]["fields"], list) and err["details"]["fields"]


def test_round_robin_after_round_bounds_ok(client):
    body = ok(client, {"format": "round_robin", "teams": teams(4), "params": {"legs": 2, "withdrawals": [{"team_id": "t1", "after_round": 6}]}})
    assert body["summary"]["forfeit"] == 0


# ---------------------------------------------------------------- single elim


def all_matches(rounds):
    return [m for r in rounds for m in r["matches"]]


MATCH_KEYS = {"match_id", "bracket", "round", "index", "home", "away", "home_seed", "away_seed", "bye", "winner", "loser", "winner_to", "loser_to"}


def test_single_elim_spec_example_n6(client):
    body = ok(client, {"format": "single_elim", "teams": teams(6), "params": {}})
    assert body["format"] == "single_elim" and body["bracket_size"] == 8
    assert len(body["rounds"]) == 3
    r1 = body["rounds"][0]["matches"]
    assert [(m["home"], m["away"], m["bye"], m["winner"]) for m in r1] == [
        ("t1", None, True, "t1"), ("t4", "t5", False, None), ("t2", None, True, "t2"), ("t3", "t6", False, None),
    ]
    assert r1[1] == {
        "match_id": "R1M2", "bracket": "main", "round": 1, "index": 2, "home": "t4", "away": "t5",
        "home_seed": 4, "away_seed": 5, "bye": False, "winner": None, "loser": None,
        "winner_to": {"match_id": "R2M1", "slot": "away"}, "loser_to": None,
    }
    r2 = body["rounds"][1]["matches"]
    assert r2[0]["home"] == "t1" and r2[0]["home_seed"] == 1 and r2[0]["away"] is None
    assert r2[1]["home"] == "t2" and r2[1]["away"] is None
    final = body["rounds"][2]["matches"][0]
    assert final["match_id"] == "R3M1" and final["winner_to"] is None


def test_seed_order_8(client):
    body = ok(client, {"format": "single_elim", "teams": teams(8)})
    seeds = [s for m in body["rounds"][0]["matches"] for s in (m["home_seed"], m["away_seed"])]
    assert seeds == [1, 8, 4, 5, 2, 7, 3, 6]


@pytest.mark.parametrize("n", list(range(2, 18)))
def test_single_elim_structure(client, n):
    body = ok(client, {"format": "single_elim", "teams": teams(n)})
    size = 1
    while size < n:
        size *= 2
    assert body["bracket_size"] == size
    k = size.bit_length() - 1
    assert [r["round"] for r in body["rounds"]] == list(range(1, k + 1))
    feeds = Counter()
    for r in body["rounds"]:
        assert len(r["matches"]) == size >> r["round"]
        for i, m in enumerate(r["matches"], start=1):
            assert set(m) == MATCH_KEYS
            assert m["match_id"] == f"R{r['round']}M{i}" and m["index"] == i and m["bracket"] == "main"
            if r["round"] < k:
                assert m["winner_to"] == {"match_id": f"R{r['round'] + 1}M{(i + 1) // 2}", "slot": "home" if i % 2 else "away"}
                feeds[(m["winner_to"]["match_id"], m["winner_to"]["slot"])] += 1
            else:
                assert m["winner_to"] is None
            assert m["loser_to"] is None
    assert all(c == 1 for c in feeds.values())
    byes = [m for m in body["rounds"][0]["matches"] if m["bye"]]
    assert len(byes) == size - n
    for m in byes:
        assert m["away"] is None and m["winner"] == m["home"]


def test_single_elim_results_propagation_and_tp(client):
    results = [
        {"match_id": "R1M2", "winner": "t5"},
        {"match_id": "R1M4", "winner": "t3"},
        {"match_id": "R2M1", "winner": "t1"},
        {"match_id": "R2M2", "winner": "t3"},
        {"match_id": "TP", "winner": "t5"},
        {"match_id": "R3M1", "winner": "t3"},
    ]
    body = ok(client, {"format": "single_elim", "teams": teams(6), "params": {"third_place_match": True, "results": results}})
    ms = {m["match_id"]: m for m in all_matches(body["rounds"])}
    assert ms["R1M2"]["winner"] == "t5" and ms["R1M2"]["loser"] == "t4"
    assert ms["R2M1"]["away"] == "t5" and ms["R2M1"]["away_seed"] == 5
    assert ms["R2M1"]["loser_to"] == {"match_id": "TP", "slot": "home"}
    assert ms["R2M2"]["loser_to"] == {"match_id": "TP", "slot": "away"}
    tp = ms["TP"]
    assert tp["bracket"] == "third_place" and set(tp) == MATCH_KEYS
    assert (tp["home"], tp["away"], tp["winner"]) == ("t5", "t2", "t5")
    assert ms["R3M1"]["home"] == "t1" and ms["R3M1"]["away"] == "t3" and ms["R3M1"]["winner"] == "t3"


@pytest.mark.parametrize(
    "results",
    [
        [{"match_id": "R9M9", "winner": "t1"}],
        [{"match_id": "R1M2", "winner": "t1"}],
        [{"match_id": "R1M1", "winner": "t8"}],
        [{"match_id": "R2M2", "winner": "t2"}],  # opponent not yet known
        [{"match_id": "R1M2"}],
        "x",
    ],
)
def test_single_elim_bad_results(client, results):
    assert_error(post(client, {"format": "single_elim", "teams": teams(6), "params": {"results": results}}), 400, "VALIDATION_ERROR")


def test_single_elim_bye_result_accepted(client):
    body = ok(client, {"format": "single_elim", "teams": teams(6), "params": {"results": [{"match_id": "R1M1", "winner": "t1"}]}})
    assert body["rounds"][0]["matches"][0]["winner"] == "t1"


# ---------------------------------------------------------------- swiss


def swiss(client, n, **params):
    return post(client, {"format": "swiss", "teams": teams(n), "params": params})


def test_swiss_round1_exact_n8(client):
    body = swiss(client, 8).json()
    assert body["round"] == 1 and body["total_rounds"] == 3 and body["bye"] is None
    assert [(p["match_id"], p["home"], p["away"]) for p in body["pairings"]] == [
        ("SW-R1-M1", "t1", "t5"), ("SW-R1-M2", "t2", "t6"), ("SW-R1-M3", "t3", "t7"), ("SW-R1-M4", "t4", "t8"),
    ]
    assert body["standings"][0] == {"rank": 1, "team_id": "t1", "score": 0.0, "buchholz": 0.0}
    assert [s["team_id"] for s in body["standings"]] == teams(8)


def test_swiss_round1_exact_n5(client):
    body = swiss(client, 5).json()
    assert body["total_rounds"] == 3 and body["bye"] == "t5"
    assert [(p["home"], p["away"]) for p in body["pairings"]] == [("t1", "t3"), ("t2", "t4")]


def test_swiss_spec_example(client):
    r = swiss(client, 5, total_rounds=3, round=2, history=[{"round": 1, "bye": "t5", "matches": [
        {"home": "t1", "away": "t3", "result": "home"}, {"home": "t2", "away": "t4", "result": "draw"}]}])
    body = r.json()
    assert r.status_code == 200, body
    assert body["bye"] == "t3"
    assert body["standings"] == [
        {"rank": 1, "team_id": "t1", "score": 1.0, "buchholz": 0.0},
        {"rank": 2, "team_id": "t5", "score": 1.0, "buchholz": 0.0},
        {"rank": 3, "team_id": "t2", "score": 0.5, "buchholz": 0.5},
        {"rank": 4, "team_id": "t4", "score": 0.5, "buchholz": 0.5},
        {"rank": 5, "team_id": "t3", "score": 0.0, "buchholz": 1.0},
    ]
    pairs = {frozenset((p["home"], p["away"])) for p in body["pairings"]}
    assert frozenset(("t2", "t4")) not in pairs and len(pairs) == 2


def brute_min(team_ids, score, played):
    best = None

    def rec(rest, acc):
        nonlocal best
        if not rest:
            best = acc if best is None else min(best, acc)
            return
        a = rest[0]
        for b in rest[1:]:
            if frozenset((a, b)) in played:
                continue
            rec([t for t in rest if t not in (a, b)], acc + abs(score[a] - score[b]))

    rec(list(team_ids), 0)
    return best


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_swiss_round2_and_3_minimal(client, n):
    outcomes = itertools.cycle(["home", "away", "draw", "home", "draw"])
    history = []
    total = min(n - 1, 4)
    for rnd in range(1, total + 1):
        r = swiss(client, n, total_rounds=total, round=rnd, history=history)
        assert r.status_code in (200, 409), r.text
        if r.status_code == 409:
            assert rnd >= 3
            assert_error(r, 409, "NO_VALID_PAIRING")
            break
        body = r.json()
        assert body["round"] == rnd
        # standings recomputed independently
        score = {t: 0.0 for t in teams(n)}
        opp = {t: [] for t in teams(n)}
        played = set()
        byes = set()
        for e in history:
            if e["bye"]:
                score[e["bye"]] += 1
                byes.add(e["bye"])
            for m in e["matches"]:
                played.add(frozenset((m["home"], m["away"])))
                opp[m["home"]].append(m["away"])
                opp[m["away"]].append(m["home"])
                if m["result"] == "home":
                    score[m["home"]] += 1
                elif m["result"] == "away":
                    score[m["away"]] += 1
                else:
                    score[m["home"]] += 0.5
                    score[m["away"]] += 0.5
        buch = {t: sum(score[o] for o in opp[t]) for t in teams(n)}
        exp_order = sorted(teams(n), key=lambda t: (-score[t], -buch[t], teams(n).index(t)))
        assert [s["team_id"] for s in body["standings"]] == exp_order
        for s in body["standings"]:
            assert s["score"] == score[s["team_id"]] and s["buchholz"] == buch[s["team_id"]]
            assert isinstance(s["score"], float) and isinstance(s["buchholz"], float)
        used = [t for p in body["pairings"] for t in (p["home"], p["away"])]
        if body["bye"]:
            used.append(body["bye"])
        assert sorted(used) == sorted(teams(n))
        assert [p["match_id"] for p in body["pairings"]] == [f"SW-R{rnd}-M{i}" for i in range(1, n // 2 + 1)]
        if rnd >= 2:
            for p in body["pairings"]:
                assert frozenset((p["home"], p["away"])) not in played
            if n % 2:
                cands = sorted((t for t in teams(n) if t not in byes), key=lambda t: (score[t], -teams(n).index(t)))
                # first candidate for which the rest can be paired
                for c in cands:
                    rest = [t for t in teams(n) if t != c]
                    m = brute_min(rest, score, played)
                    if m is not None:
                        assert body["bye"] == c
                        break
                rest = [t for t in teams(n) if t != body["bye"]]
            else:
                rest = teams(n)
            cost = sum(abs(score[p["home"]] - score[p["away"]]) for p in body["pairings"])
            assert cost == brute_min(rest, score, played)
        history.append({
            "round": rnd,
            "bye": body["bye"],
            "matches": [dict(home=p["home"], away=p["away"], result=next(outcomes)) for p in body["pairings"]],
        })


def test_swiss_no_valid_pairing(client):
    history = [
        {"round": 1, "bye": None, "matches": [dict(home="t1", away="t4", result="home"), dict(home="t2", away="t5", result="home"), dict(home="t3", away="t6", result="home")]},
        {"round": 2, "bye": None, "matches": [dict(home="t1", away="t5", result="home"), dict(home="t2", away="t6", result="home"), dict(home="t3", away="t4", result="home")]},
        {"round": 3, "bye": None, "matches": [dict(home="t1", away="t6", result="home"), dict(home="t2", away="t4", result="home"), dict(home="t3", away="t5", result="home")]},
    ]
    err = assert_error(swiss(client, 6, total_rounds=5, round=4, history=history), 409, "NO_VALID_PAIRING")
    assert err["details"] == {"round": 4}


@pytest.mark.parametrize(
    "params",
    [
        {"round": 2, "history": []},
        {"round": 1, "history": [{"round": 1, "bye": None, "matches": []}]},
        {"total_rounds": 8},
        {"total_rounds": 0},
        {"round": 4, "total_rounds": 3},
        {"round": 2, "history": [{"round": 1, "bye": None, "matches": [dict(home="t1", away="zz", result="home")]}]},
        {"round": 2, "history": [{"round": 1, "bye": None, "matches": [dict(home="t1", away="t2", result="win")]}]},
        {"round": 2, "history": [{"round": 1, "bye": None, "matches": [dict(home="t1", away="t2", result="home"), dict(home="t1", away="t3", result="home")]}]},
        {"round": 3, "total_rounds": 3, "history": [{"round": 1, "bye": None, "matches": []}, {"round": 1, "bye": None, "matches": []}]},
    ],
)
def test_swiss_validation(client, params):
    assert_error(swiss(client, 8, **params), 400, "VALIDATION_ERROR")


def test_swiss_large_n_fast(client):
    import time

    n = 64
    outcomes = itertools.cycle(["home", "away", "draw"])
    history = []
    for rnd in range(1, 13):
        start = time.time()
        r = swiss(client, n, total_rounds=20, round=rnd, history=history)
        assert r.status_code == 200, r.text
        assert time.time() - start < 3
        body = r.json()
        assert len(body["pairings"]) == 32
        history.append({"round": rnd, "bye": None, "matches": [dict(home=p["home"], away=p["away"], result=next(outcomes)) for p in body["pairings"]]})


def test_blossom_matches_exhaustive_search():
    import random

    from backend.fixtures import swiss as sw

    rng = random.Random(7)
    for _ in range(300):
        m = rng.choice([2, 4, 6, 8, 10, 12])
        score = sorted((rng.randint(0, 6) for _ in range(m)), reverse=True)
        order = list(range(m))
        p = rng.choice([0.0, 0.3, 0.6])
        played = {frozenset((i, j)) for i in range(m) for j in range(i + 1, m) if rng.random() < p}
        exact = sw._min_pairing(order, score, played)
        fast = sw._blossom_min_pairing(order, score, played)
        assert (exact is None) == (fast is None)
        if exact is not None:
            assert sorted(t for pr in fast for t in pr) == order
            assert all(frozenset(pr) not in played for pr in fast)
            cost = lambda pairs: sum(abs(score[a] - score[b]) for a, b in pairs)  # noqa: E731
            assert cost(exact) == cost(fast)


# ---------------------------------------------------------------- double elim


def de(client, n, **params):
    return post(client, {"format": "double_elim", "teams": teams(n), "params": params})


def check_double_structure(body, n):
    size = 1
    while size < n:
        size *= 2
    k = size.bit_length() - 1
    assert body["bracket_size"] == size
    assert [r["round"] for r in body["winners"]] == list(range(1, k + 1))
    assert [r["round"] for r in body["losers"]] == list(range(1, 2 * (k - 1) + 1))
    for r in body["winners"]:
        assert len(r["matches"]) == size >> r["round"]
        for i, m in enumerate(r["matches"], start=1):
            assert m["match_id"] == f"WR{r['round']}M{i}" and m["bracket"] == "winners"
            assert m["winner_to"] is not None and m["loser_to"] is not None
    for r in body["losers"]:
        j = (r["round"] + 1) // 2
        assert len(r["matches"]) == size >> (j + 1)
        for i, m in enumerate(r["matches"], start=1):
            assert m["match_id"] == f"LR{r['round']}M{i}" and m["bracket"] == "losers"
            assert m["winner_to"] is not None and m["loser_to"] is None
    assert sum(len(r["matches"]) for r in body["losers"]) == size - 2
    matches = all_matches(body["winners"]) + all_matches(body["losers"]) + body["grand_final"]
    for m in matches:
        assert MATCH_KEYS <= set(m)
    feeds = Counter()
    for m in matches:
        for key in ("winner_to", "loser_to"):
            if m[key]:
                feeds[(m[key]["match_id"], m[key]["slot"])] += 1
    for m in matches:
        if m["match_id"].startswith("WR1M"):
            assert feeds[(m["match_id"], "home")] == 0 and feeds[(m["match_id"], "away")] == 0
        else:
            assert feeds[(m["match_id"], "home")] == 1, m["match_id"]
            assert feeds[(m["match_id"], "away")] == 1, m["match_id"]
    wr_final = body["winners"][-1]["matches"][0]
    lb_final = body["losers"][-1]["matches"][0]
    assert wr_final["winner_to"] == {"match_id": "GF1", "slot": "home"}
    assert wr_final["loser_to"] == {"match_id": lb_final["match_id"], "slot": "away"}
    assert lb_final["winner_to"] == {"match_id": "GF1", "slot": "away"}
    return matches


def test_double_elim_n8_counts_and_routing(client):
    r = de(client, 8, bracket_reset=True)
    body = r.json()
    assert r.status_code == 200, body
    assert body["format"] == "double_elim" and body["bracket_reset"] is True
    check_double_structure(body, 8)
    assert [len(r["matches"]) for r in body["winners"]] == [4, 2, 1]
    assert [len(r["matches"]) for r in body["losers"]] == [2, 2, 1, 1]
    seeds = [s for m in body["winners"][0]["matches"] for s in (m["home_seed"], m["away_seed"])]
    assert seeds == [1, 8, 4, 5, 2, 7, 3, 6]
    gf1, gf2 = body["grand_final"]
    assert gf1["match_id"] == "GF1" and gf2["match_id"] == "GF2"
    assert gf2["conditional"] is True and gf2["required"] is None
    assert gf1["bracket"] == gf2["bracket"] == "grand_final"


def play_all(client, n, reset, pick, gf1_pick):
    """Repeatedly submit results (lower seed wins unless pick says otherwise) until GF1 decided."""
    results: list[dict] = []
    for _ in range(64):
        body = de(client, n, bracket_reset=reset, results=results).json()
        matches = all_matches(body["winners"]) + all_matches(body["losers"]) + body["grand_final"][:1]
        decided = {x["match_id"] for x in results}
        progress = False
        for m in matches:
            if m["winner"] is None and m["home"] and m["away"] and m["match_id"] not in decided:
                if m["match_id"] == "GF1":
                    w = m[gf1_pick]
                else:
                    w = pick(m)
                results.append({"match_id": m["match_id"], "winner": w})
                progress = True
        if not progress:
            return body, results
    raise AssertionError("did not converge")


@pytest.mark.parametrize("n", [3, 5, 6, 8, 11])
@pytest.mark.parametrize("gf1_pick", ["home", "away"])
def test_double_elim_full_run_and_gf2(client, n, gf1_pick):
    body, results = play_all(client, n, True, lambda m: m["home"], gf1_pick)
    matches = check_double_structure(body, n)
    gf1, gf2 = body["grand_final"]
    assert gf1["winner"] == gf1[gf1_pick]
    assert {gf2["home"], gf2["away"]} == {gf1["home"], gf1["away"]}
    assert gf2["required"] is (gf1_pick == "away")
    # every team except the champion lost... results propagated: each winner sits in its winner_to slot
    by_id = {m["match_id"]: m for m in matches}
    for m in matches:
        for key, team_key in (("winner_to", "winner"), ("loser_to", "loser")):
            if m[team_key] and m[key]:
                assert by_id[m[key]["match_id"]][m[key]["slot"]] == m[team_key]
    # a team appears in the losers bracket at most... every team except two lost at least once
    if gf1_pick == "away":
        r = de(client, n, bracket_reset=True, results=results + [{"match_id": "GF2", "winner": gf2["home"]}])
        assert r.status_code == 200, r.text
        assert r.json()["grand_final"][1]["winner"] == gf2["home"]
    else:
        assert_error(de(client, n, bracket_reset=True, results=results + [{"match_id": "GF2", "winner": gf2["home"]}]), 400, "VALIDATION_ERROR")


def test_double_elim_no_reset(client):
    body, _ = play_all(client, 6, False, lambda m: m["away"], "away")
    assert body["bracket_reset"] is False
    assert len(body["grand_final"]) == 1
    gf1 = body["grand_final"][0]
    assert gf1["winner"] == gf1["away"] and gf1["winner_to"] is None


def test_double_elim_n3_and_n6_byes(client):
    body = de(client, 3).json()
    check_double_structure(body, 3)
    assert body["winners"][0]["matches"][0]["bye"] is True
    body = de(client, 6, results=[{"match_id": "WR1M2", "winner": "t5"}]).json()
    check_double_structure(body, 6)
    lr1 = body["losers"][0]["matches"][0]
    assert lr1["winner"] == "t4"
    assert_error(de(client, 6, results=[{"match_id": "LR9M1", "winner": "t1"}]), 400, "VALIDATION_ERROR")
    assert_error(de(client, 8, results=[{"match_id": "WR1M1", "winner": "t2"}]), 400, "VALIDATION_ERROR")
