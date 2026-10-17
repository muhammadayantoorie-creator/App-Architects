"""Fixture and bracket generation for POST /audit/v1/fixtures.

Pure computation: nothing here touches the database or Redis.
"""

from __future__ import annotations

from typing import Any, Callable

from backend.core.errors import ApiError


def validation_error(fields: list[str], message: str = "Request validation failed") -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, {"fields": list(fields)})


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def get_bool(params: dict[str, Any], key: str, default: bool) -> bool:
    value = params.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise validation_error([f"params.{key}"])
    return value


def next_pow2(n: int) -> int:
    size = 1
    while size < n:
        size *= 2
    return size


def seed_order(size: int) -> list[int]:
    """order(2)=[1,2]; order(2k) = for each s in order(k): [s, 2k+1-s]."""
    order = [1]
    current = 1
    while current < size:
        current *= 2
        order = [x for s in order for x in (s, current + 1 - s)]
    return order


class _Dead:
    """Marks a slot (or result) that will never hold a team (bye)."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "DEAD"


DEAD = _Dead()


def _is_team(value: Any) -> bool:
    return isinstance(value, str)


class Bracket:
    """Generic elimination bracket: matches, routing and result propagation."""

    def __init__(self, seeds: dict[str, int]) -> None:
        self.seeds = seeds
        self.matches: dict[str, dict[str, Any]] = {}
        self.sequence: list[dict[str, Any]] = []

    def add(
        self,
        match_id: str,
        bracket: str,
        rnd: int,
        index: int,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        match = {
            "match_id": match_id,
            "bracket": bracket,
            "round": rnd,
            "index": index,
            "home": None,
            "away": None,
            "winner": None,
            "loser": None,
            "winner_to": None,
            "loser_to": None,
            "bye": False,
            "extra": dict(extra or {}),
            "gate": None,
        }
        self.matches[match_id] = match
        self.sequence.append(match)
        return match

    def link(self, source: str, kind: str, target: str, slot: str) -> None:
        self.matches[source][f"{kind}_to"] = {"match_id": target, "slot": slot}

    def parse_results(self, params: dict[str, Any]) -> dict[str, str]:
        raw = params.get("results")
        if raw is None:
            return {}
        if not isinstance(raw, list):
            raise validation_error(["params.results"])
        results: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise validation_error(["params.results"])
            match_id = item.get("match_id")
            winner = item.get("winner")
            if not isinstance(match_id, str) or not isinstance(winner, str):
                raise validation_error(["params.results"])
            if match_id not in self.matches:
                raise validation_error(["params.results"], f"Unknown match_id {match_id}")
            if match_id in results and results[match_id] != winner:
                raise validation_error(["params.results"], f"Conflicting results for {match_id}")
            results[match_id] = winner
        return results

    def resolve(self, results: dict[str, str]) -> None:
        changed = True
        while changed:
            changed = False
            for match in self.sequence:
                home, away = match["home"], match["away"]
                if home is DEAD or away is DEAD:
                    match["bye"] = True
                if match["winner"] is None:
                    outcome: tuple[Any, Any] | None = None
                    if home is DEAD and away is DEAD:
                        outcome = (DEAD, DEAD)
                    elif home is DEAD and _is_team(away):
                        outcome = (away, DEAD)
                    elif away is DEAD and _is_team(home):
                        outcome = (home, DEAD)
                    elif _is_team(home) and _is_team(away):
                        wanted = results.get(match["match_id"])
                        gate: Callable[[], bool] | None = match["gate"]
                        if wanted in (home, away) and (gate is None or gate()):
                            outcome = (wanted, away if wanted == home else home)
                    if outcome is not None:
                        match["winner"], match["loser"] = outcome
                        changed = True
                for kind in ("winner", "loser"):
                    value = match[kind]
                    target = match[f"{kind}_to"]
                    if value is None or target is None:
                        continue
                    dest = self.matches[target["match_id"]]
                    if dest[target["slot"]] is None:
                        dest[target["slot"]] = value
                        changed = True
        for match_id, wanted in results.items():
            if self.matches[match_id]["winner"] != wanted:
                raise validation_error(
                    ["params.results"],
                    f"Winner {wanted} is not a participant of {match_id}",
                )

    def team(self, value: Any) -> str | None:
        return value if _is_team(value) else None

    def seed(self, value: Any) -> int | None:
        return self.seeds.get(value) if _is_team(value) else None

    def render(self, match: dict[str, Any]) -> dict[str, Any]:
        out = {
            "match_id": match["match_id"],
            "bracket": match["bracket"],
            "round": match["round"],
            "index": match["index"],
            "home": self.team(match["home"]),
            "away": self.team(match["away"]),
            "home_seed": self.seed(match["home"]),
            "away_seed": self.seed(match["away"]),
            "bye": match["bye"],
            "winner": self.team(match["winner"]),
            "loser": self.team(match["loser"]),
            "winner_to": match["winner_to"],
            "loser_to": match["loser_to"],
        }
        out.update(match["extra"])
        return out


def seed_first_round(bracket: Bracket, teams: list[str], size: int, prefix: str) -> None:
    """Round-1 seeding shared by single and double elimination (exact)."""
    order = seed_order(size)
    n = len(teams)
    for i in range(1, size // 2 + 1):
        a, b = order[2 * i - 2], order[2 * i - 1]
        low, high = min(a, b), max(a, b)
        match = bracket.matches[f"{prefix}1M{i}"]
        match["home"] = teams[low - 1] if low <= n else DEAD
        match["away"] = teams[high - 1] if high <= n else DEAD
