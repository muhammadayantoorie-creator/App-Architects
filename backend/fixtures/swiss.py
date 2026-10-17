"""Swiss system: pairs one round per call."""

from __future__ import annotations

from typing import Any

from backend.core.errors import ApiError
from backend.fixtures import is_int, validation_error

RESULTS = ("home", "away", "draw")
_INF = float("inf")
# Up to this many teams the exact memoised search is used; above it the
# (equally exact) weighted blossom algorithm keeps the runtime polynomial.
EXHAUSTIVE_LIMIT = 16


def _max_weight_matching(nvertex: int, edges: list[tuple[int, int, int]]) -> list[int]:
    """Maximum-weight maximum-cardinality matching (Edmonds' blossom algorithm,
    after J. van Rantwijk's reference implementation). Integer weights only.
    Returns mate[v] (vertex index or -1)."""
    if not edges:
        return [-1] * nvertex
    nedge = len(edges)
    maxweight = max(0, max(w for (_i, _j, w) in edges))
    endpoint = [edges[p // 2][p % 2] for p in range(2 * nedge)]
    neighbend: list[list[int]] = [[] for _ in range(nvertex)]
    for k, (i, j, _w) in enumerate(edges):
        neighbend[i].append(2 * k + 1)
        neighbend[j].append(2 * k)
    mate = [-1] * nvertex
    label = [0] * (2 * nvertex)
    labelend = [-1] * (2 * nvertex)
    inblossom = list(range(nvertex))
    blossomparent = [-1] * (2 * nvertex)
    blossomchilds: list[Any] = [None] * (2 * nvertex)
    blossombase = list(range(nvertex)) + [-1] * nvertex
    blossomendps: list[Any] = [None] * (2 * nvertex)
    bestedge = [-1] * (2 * nvertex)
    blossombestedges: list[Any] = [None] * (2 * nvertex)
    unusedblossoms = list(range(nvertex, 2 * nvertex))
    dualvar = [maxweight] * nvertex + [0] * nvertex
    allowedge = [False] * nedge
    queue: list[int] = []

    def slack(k: int) -> int:
        i, j, wt = edges[k]
        return dualvar[i] + dualvar[j] - 2 * wt

    def blossom_leaves(b: int):
        if b < nvertex:
            yield b
        else:
            for t in blossomchilds[b]:
                if t < nvertex:
                    yield t
                else:
                    yield from blossom_leaves(t)

    def assign_label(w: int, t: int, p: int) -> None:
        b = inblossom[w]
        label[w] = label[b] = t
        labelend[w] = labelend[b] = p
        bestedge[w] = bestedge[b] = -1
        if t == 1:
            queue.extend(blossom_leaves(b))
        elif t == 2:
            base = blossombase[b]
            assign_label(endpoint[mate[base]], 1, mate[base] ^ 1)

    def scan_blossom(v: int, w: int) -> int:
        path = []
        base = -1
        while v != -1 or w != -1:
            b = inblossom[v]
            if label[b] & 4:
                base = blossombase[b]
                break
            path.append(b)
            label[b] = 5
            if labelend[b] == -1:
                v = -1
            else:
                v = endpoint[labelend[b]]
                b = inblossom[v]
                v = endpoint[labelend[b]]
            if w != -1:
                v, w = w, v
        for b in path:
            label[b] = 1
        return base

    def add_blossom(base: int, k: int) -> None:
        v, w, _wt = edges[k]
        bb = inblossom[base]
        bv = inblossom[v]
        bw = inblossom[w]
        b = unusedblossoms.pop()
        blossombase[b] = base
        blossomparent[b] = -1
        blossomparent[bb] = b
        path: list[int] = []
        endps: list[int] = []
        blossomchilds[b] = path
        blossomendps[b] = endps
        while bv != bb:
            blossomparent[bv] = b
            path.append(bv)
            endps.append(labelend[bv])
            v = endpoint[labelend[bv]]
            bv = inblossom[v]
        path.append(bb)
        path.reverse()
        endps.reverse()
        endps.append(2 * k)
        while bw != bb:
            blossomparent[bw] = b
            path.append(bw)
            endps.append(labelend[bw] ^ 1)
            w = endpoint[labelend[bw]]
            bw = inblossom[w]
        label[b] = 1
        labelend[b] = labelend[bb]
        dualvar[b] = 0
        for leaf in blossom_leaves(b):
            if label[inblossom[leaf]] == 2:
                queue.append(leaf)
            inblossom[leaf] = b
        bestedgeto = [-1] * (2 * nvertex)
        for child in path:
            if blossombestedges[child] is None:
                nblists = [[p // 2 for p in neighbend[leaf]] for leaf in blossom_leaves(child)]
            else:
                nblists = [blossombestedges[child]]
            for nblist in nblists:
                for kk in nblist:
                    i, j, _w = edges[kk]
                    if inblossom[j] == b:
                        i, j = j, i
                    bj = inblossom[j]
                    if bj != b and label[bj] == 1 and (
                        bestedgeto[bj] == -1 or slack(kk) < slack(bestedgeto[bj])
                    ):
                        bestedgeto[bj] = kk
            blossombestedges[child] = None
            bestedge[child] = -1
        blossombestedges[b] = [kk for kk in bestedgeto if kk != -1]
        bestedge[b] = -1
        for kk in blossombestedges[b]:
            if bestedge[b] == -1 or slack(kk) < slack(bestedge[b]):
                bestedge[b] = kk

    def expand_blossom(b: int, endstage: bool) -> None:
        for s in blossomchilds[b]:
            blossomparent[s] = -1
            if s < nvertex:
                inblossom[s] = s
            elif endstage and dualvar[s] == 0:
                expand_blossom(s, endstage)
            else:
                for leaf in blossom_leaves(s):
                    inblossom[leaf] = s
        if (not endstage) and label[b] == 2:
            entrychild = inblossom[endpoint[labelend[b] ^ 1]]
            j = blossomchilds[b].index(entrychild)
            if j & 1:
                j -= len(blossomchilds[b])
                jstep = 1
                endptrick = 0
            else:
                jstep = -1
                endptrick = 1
            p = labelend[b]
            while j != 0:
                label[endpoint[p ^ 1]] = 0
                label[endpoint[blossomendps[b][j - endptrick] ^ endptrick ^ 1]] = 0
                assign_label(endpoint[p ^ 1], 2, p)
                allowedge[blossomendps[b][j - endptrick] // 2] = True
                j += jstep
                p = blossomendps[b][j - endptrick] ^ endptrick
                allowedge[p // 2] = True
                j += jstep
            bv = blossomchilds[b][j]
            label[endpoint[p ^ 1]] = label[bv] = 2
            labelend[endpoint[p ^ 1]] = labelend[bv] = p
            bestedge[bv] = -1
            j += jstep
            while blossomchilds[b][j] != entrychild:
                bv = blossomchilds[b][j]
                if label[bv] == 1:
                    j += jstep
                    continue
                found = -1
                for leaf in blossom_leaves(bv):
                    if label[leaf] != 0:
                        found = leaf
                        break
                if found != -1:
                    label[found] = 0
                    label[endpoint[mate[blossombase[bv]]]] = 0
                    assign_label(found, 2, labelend[found])
                j += jstep
        label[b] = labelend[b] = -1
        blossomchilds[b] = blossomendps[b] = None
        blossombase[b] = -1
        blossombestedges[b] = None
        bestedge[b] = -1
        unusedblossoms.append(b)

    def augment_blossom(b: int, v: int) -> None:
        t = v
        while blossomparent[t] != b:
            t = blossomparent[t]
        if t >= nvertex:
            augment_blossom(t, v)
        i = j = blossomchilds[b].index(t)
        if i & 1:
            j -= len(blossomchilds[b])
            jstep = 1
            endptrick = 0
        else:
            jstep = -1
            endptrick = 1
        while j != 0:
            j += jstep
            t = blossomchilds[b][j]
            p = blossomendps[b][j - endptrick] ^ endptrick
            if t >= nvertex:
                augment_blossom(t, endpoint[p])
            j += jstep
            t = blossomchilds[b][j]
            if t >= nvertex:
                augment_blossom(t, endpoint[p ^ 1])
            mate[endpoint[p]] = p ^ 1
            mate[endpoint[p ^ 1]] = p
        blossomchilds[b] = blossomchilds[b][i:] + blossomchilds[b][:i]
        blossomendps[b] = blossomendps[b][i:] + blossomendps[b][:i]
        blossombase[b] = blossombase[blossomchilds[b][0]]

    def augment_matching(k: int) -> None:
        v, w, _wt = edges[k]
        for s, p in ((v, 2 * k + 1), (w, 2 * k)):
            while True:
                bs = inblossom[s]
                if bs >= nvertex:
                    augment_blossom(bs, s)
                mate[s] = p
                if labelend[bs] == -1:
                    break
                t = endpoint[labelend[bs]]
                bt = inblossom[t]
                s = endpoint[labelend[bt]]
                j = endpoint[labelend[bt] ^ 1]
                if bt >= nvertex:
                    augment_blossom(bt, j)
                mate[j] = labelend[bt]
                p = labelend[bt] ^ 1

    for _stage in range(nvertex):
        label[:] = [0] * (2 * nvertex)
        bestedge[:] = [-1] * (2 * nvertex)
        blossombestedges[nvertex:] = [None] * nvertex
        allowedge[:] = [False] * nedge
        queue[:] = []
        for v in range(nvertex):
            if mate[v] == -1 and label[inblossom[v]] == 0:
                assign_label(v, 1, -1)
        augmented = False
        while True:
            while queue and not augmented:
                v = queue.pop()
                for p in neighbend[v]:
                    k = p // 2
                    w = endpoint[p]
                    if inblossom[v] == inblossom[w]:
                        continue
                    kslack = 0
                    if not allowedge[k]:
                        kslack = slack(k)
                        if kslack <= 0:
                            allowedge[k] = True
                    if allowedge[k]:
                        if label[inblossom[w]] == 0:
                            assign_label(w, 2, p ^ 1)
                        elif label[inblossom[w]] == 1:
                            base = scan_blossom(v, w)
                            if base >= 0:
                                add_blossom(base, k)
                            else:
                                augment_matching(k)
                                augmented = True
                                break
                        elif label[w] == 0:
                            label[w] = 2
                            labelend[w] = p ^ 1
                    elif label[inblossom[w]] == 1:
                        b = inblossom[v]
                        if bestedge[b] == -1 or kslack < slack(bestedge[b]):
                            bestedge[b] = k
                    elif label[w] == 0:
                        if bestedge[w] == -1 or kslack < slack(bestedge[w]):
                            bestedge[w] = k
            if augmented:
                break
            deltatype = -1
            delta = 0
            deltaedge = -1
            deltablossom = -1
            for v in range(nvertex):
                if label[inblossom[v]] == 0 and bestedge[v] != -1:
                    d = slack(bestedge[v])
                    if deltatype == -1 or d < delta:
                        delta = d
                        deltatype = 2
                        deltaedge = bestedge[v]
            for b in range(2 * nvertex):
                if blossomparent[b] == -1 and label[b] == 1 and bestedge[b] != -1:
                    d = slack(bestedge[b]) // 2
                    if deltatype == -1 or d < delta:
                        delta = d
                        deltatype = 3
                        deltaedge = bestedge[b]
            for b in range(nvertex, 2 * nvertex):
                if (
                    blossombase[b] >= 0
                    and blossomparent[b] == -1
                    and label[b] == 2
                    and (deltatype == -1 or dualvar[b] < delta)
                ):
                    delta = dualvar[b]
                    deltatype = 4
                    deltablossom = b
            if deltatype == -1:
                deltatype = 1
                delta = max(0, min(dualvar[:nvertex]))
            for v in range(nvertex):
                if label[inblossom[v]] == 1:
                    dualvar[v] -= delta
                elif label[inblossom[v]] == 2:
                    dualvar[v] += delta
            for b in range(nvertex, 2 * nvertex):
                if blossombase[b] >= 0 and blossomparent[b] == -1:
                    if label[b] == 1:
                        dualvar[b] += delta
                    elif label[b] == 2:
                        dualvar[b] -= delta
            if deltatype == 1:
                break
            if deltatype == 2:
                allowedge[deltaedge] = True
                i, j, _wt = edges[deltaedge]
                if label[inblossom[i]] == 0:
                    i, j = j, i
                queue.append(i)
            elif deltatype == 3:
                allowedge[deltaedge] = True
                i, j, _wt = edges[deltaedge]
                queue.append(i)
            else:
                expand_blossom(deltablossom, False)
        if not augmented:
            break
        for b in range(nvertex, 2 * nvertex):
            if blossomparent[b] == -1 and blossombase[b] >= 0 and label[b] == 1 and dualvar[b] == 0:
                expand_blossom(b, True)
    return [endpoint[mate[v]] if mate[v] >= 0 else -1 for v in range(nvertex)]


def _blossom_min_pairing(
    order: list[int], score: list[int], played: set[frozenset[int]]
) -> list[tuple[int, int]] | None:
    m = len(order)
    sc = [score[t] for t in order]
    big = (max(sc) - min(sc)) + 1
    edges = [
        (i, j, 2 * (big - (sc[i] - sc[j])))
        for i in range(m)
        for j in range(i + 1, m)
        if frozenset((order[i], order[j])) not in played
    ]
    mate = _max_weight_matching(m, edges)
    if any(x == -1 for x in mate):
        return None
    return [(order[i], order[mate[i]]) for i in range(m) if i < mate[i]]


def _parse_history(
    teams: list[str], index: dict[str, int], raw: Any, current_round: int
) -> list[dict[str, Any]]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise validation_error(["params.history"])
    seen_rounds: set[int] = set()
    parsed: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise validation_error(["params.history"])
        rnd = entry.get("round")
        if not is_int(rnd) or not 1 <= rnd < current_round or rnd in seen_rounds:
            raise validation_error(["params.history"], "History must contain exactly rounds 1..round-1")
        seen_rounds.add(rnd)
        bye = entry.get("bye")
        if bye is not None and (not isinstance(bye, str) or bye not in index):
            raise validation_error(["params.history"], "Unknown bye team")
        matches = entry.get("matches")
        if matches is None:
            matches = []
        if not isinstance(matches, list):
            raise validation_error(["params.history"])
        used: set[str] = {bye} if bye is not None else set()
        parsed_matches = []
        for match in matches:
            if not isinstance(match, dict):
                raise validation_error(["params.history"])
            home, away, result = match.get("home"), match.get("away"), match.get("result")
            if not isinstance(home, str) or home not in index or not isinstance(away, str) or away not in index:
                raise validation_error(["params.history"], "Unknown team in history")
            if home == away or home in used or away in used:
                raise validation_error(["params.history"], "Team appears twice in a round")
            if not isinstance(result, str) or result not in RESULTS:
                raise validation_error(["params.history"], "result must be home|away|draw")
            used.update((home, away))
            parsed_matches.append((index[home], index[away], result))
        parsed.append({"round": rnd, "bye": index[bye] if bye is not None else None, "matches": parsed_matches})
    if seen_rounds != set(range(1, current_round)):
        raise validation_error(["params.history"], "History must contain exactly rounds 1..round-1")
    parsed.sort(key=lambda e: e["round"])
    return parsed


def _min_pairing(
    order: list[int], score: list[int], played: set[frozenset[int]]
) -> list[tuple[int, int]] | None:
    """Rematch-free perfect matching of `order` (standings order, score desc)
    minimising the sum of |score difference|. Exact memoised search with an
    admissible lower bound (adjacent pairing ignoring rematches)."""
    m = len(order)
    if m == 0:
        return []
    if m % 2:
        return None
    if m > EXHAUSTIVE_LIMIT:
        return _blossom_min_pairing(order, score, played)
    sc = [score[t] for t in order]
    adj = [0] * m
    for i in range(m):
        for j in range(m):
            if i != j and frozenset((order[i], order[j])) not in played:
                adj[i] |= 1 << j
    memo: dict[int, tuple[float, int]] = {}

    def lower_bound(mask: int) -> int:
        total = 0
        prev = -1
        while mask:
            low = mask & -mask
            i = low.bit_length() - 1
            mask ^= low
            if prev < 0:
                prev = i
            else:
                total += sc[prev] - sc[i]
                prev = -1
        return total

    def rec(mask: int) -> float:
        if mask == 0:
            return 0
        cached = memo.get(mask)
        if cached is not None:
            return cached[0]
        # Quick infeasibility check: some team has no allowed partner left.
        probe = mask
        while probe:
            low_p = probe & -probe
            if not adj[low_p.bit_length() - 1] & mask:
                memo[mask] = (_INF, -1)
                return _INF
            probe ^= low_p
        floor = lower_bound(mask)
        low = mask & -mask
        i = low.bit_length() - 1
        rest = mask ^ low
        best: float = _INF
        best_j = -1
        remaining = rest & adj[i]
        while remaining:
            low_j = remaining & -remaining
            j = low_j.bit_length() - 1
            remaining ^= low_j
            cost = sc[i] - sc[j]
            if cost >= best:
                break
            sub_mask = rest ^ low_j
            if cost + lower_bound(sub_mask) >= best:
                continue
            sub = rec(sub_mask)
            if cost + sub < best:
                best = cost + sub
                best_j = j
                if best <= floor:
                    break  # cannot do better than the unconstrained optimum
        memo[mask] = (best, best_j)
        return best

    full = (1 << m) - 1
    if rec(full) == _INF:
        return None
    pairs: list[tuple[int, int]] = []
    mask = full
    while mask:
        low = mask & -mask
        i = low.bit_length() - 1
        j = memo[mask][1]
        pairs.append((order[i], order[j]))
        mask ^= low | (1 << j)
    return pairs


def generate(teams: list[str], params: dict[str, Any]) -> dict[str, Any]:
    n = len(teams)
    index = {team: i for i, team in enumerate(teams)}

    total_rounds = params.get("total_rounds")
    if total_rounds is None:
        total_rounds = (n - 1).bit_length()  # ceil(log2 n)
    if not is_int(total_rounds) or not 1 <= total_rounds <= n - 1:
        raise validation_error(["params.total_rounds"])
    current = params.get("round")
    if current is None:
        current = 1
    if not is_int(current) or not 1 <= current <= total_rounds:
        raise validation_error(["params.round"])
    history = _parse_history(teams, index, params.get("history"), current)

    # Scores in half points (win 2, draw 1, bye 2).
    score = [0] * n
    opponents: list[list[int]] = [[] for _ in range(n)]
    played: set[frozenset[int]] = set()
    had_bye: set[int] = set()
    for entry in history:
        if entry["bye"] is not None:
            score[entry["bye"]] += 2
            had_bye.add(entry["bye"])
        for home, away, result in entry["matches"]:
            if result == "home":
                score[home] += 2
            elif result == "away":
                score[away] += 2
            else:
                score[home] += 1
                score[away] += 1
            opponents[home].append(away)
            opponents[away].append(home)
            played.add(frozenset((home, away)))
    buchholz = [sum(score[o] for o in opponents[t]) for t in range(n)]
    order = sorted(range(n), key=lambda t: (-score[t], -buchholz[t], t))
    standings = [
        {"rank": rank, "team_id": teams[t], "score": score[t] / 2, "buchholz": buchholz[t] / 2}
        for rank, t in enumerate(order, start=1)
    ]

    bye: int | None = None
    if current == 1:
        half = n // 2
        pairs = [(i, i + half) for i in range(half)]
        if n % 2:
            bye = n - 1
    else:
        pairs_found: list[tuple[int, int]] | None = None
        if n % 2:
            candidates = sorted(
                (t for t in range(n) if t not in had_bye), key=lambda t: (score[t], -t)
            )
            for candidate in candidates:
                rest = [t for t in order if t != candidate]
                pairs_found = _min_pairing(rest, score, played)
                if pairs_found is not None:
                    bye = candidate
                    break
        else:
            pairs_found = _min_pairing(order, score, played)
        if pairs_found is None:
            raise ApiError(
                409,
                "NO_VALID_PAIRING",
                f"No rematch-free pairing exists for round {current}",
                {"round": current},
            )
        pairs = pairs_found

    pairings = [
        {"match_id": f"SW-R{current}-M{k}", "home": teams[home], "away": teams[away]}
        for k, (home, away) in enumerate(pairs, start=1)
    ]
    return {
        "format": "swiss",
        "round": current,
        "total_rounds": total_rounds,
        "pairings": pairings,
        "bye": teams[bye] if bye is not None else None,
        "standings": standings,
    }
