"""Swiss system: pairs one round per call."""

from __future__ import annotations

from typing import Any

from backend.core.errors import ApiError
from backend.fixtures import is_int, validation_error

RESULTS = ("home", "away", "draw")
_INF = float("inf")


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
    sc = [score[t] for t in order]
    allowed = [
        [i != j and frozenset((order[i], order[j])) not in played for j in range(m)]
        for i in range(m)
    ]
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
        low = mask & -mask
        i = low.bit_length() - 1
        rest = mask ^ low
        best: float = _INF
        best_j = -1
        row = allowed[i]
        remaining = rest
        while remaining:
            low_j = remaining & -remaining
            j = low_j.bit_length() - 1
            remaining ^= low_j
            if not row[j]:
                continue
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
