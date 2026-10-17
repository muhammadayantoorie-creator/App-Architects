"""Round robin via the circle method (legs 1|2, byes, withdrawals)."""

from __future__ import annotations

from typing import Any

from backend.fixtures import is_int, validation_error

POLICIES = ("void_all", "forfeit_remaining")


def _base_rounds(teams: list[str]) -> list[tuple[list[tuple[str, str]], list[str]]]:
    """One leg: list of (pairs[(home, away)], byes) per round."""
    slots: list[str | None] = list(teams)
    if len(slots) % 2:
        slots.append(None)
    size = len(slots)
    fixed = slots[-1]
    rotating = slots[:-1]
    rounds = []
    for r in range(size - 1):
        arr = rotating[r:] + rotating[:r] + [fixed]
        pairs: list[tuple[str, str]] = []
        byes: list[str] = []
        for i in range(size // 2):
            a, b = arr[i], arr[size - 1 - i]
            if i == 0 and r % 2 == 1:
                a, b = b, a
            if a is None:
                byes.append(b)  # type: ignore[arg-type]
            elif b is None:
                byes.append(a)
            else:
                pairs.append((a, b))
        rounds.append((pairs, byes))
    return rounds


def generate(teams: list[str], params: dict[str, Any]) -> dict[str, Any]:
    legs = params.get("legs")
    if legs is None:
        legs = 1
    if not is_int(legs) or legs not in (1, 2):
        raise validation_error(["params.legs"])

    policy = params.get("withdrawal_policy")
    if policy is None:
        policy = "forfeit_remaining"
    if not isinstance(policy, str) or policy not in POLICIES:
        raise validation_error(["params.withdrawal_policy"])

    n = len(teams)
    per_leg = n - 1 if n % 2 == 0 else n
    round_count = per_leg * legs

    raw_withdrawals = params.get("withdrawals")
    if raw_withdrawals is None:
        raw_withdrawals = []
    if not isinstance(raw_withdrawals, list):
        raise validation_error(["params.withdrawals"])
    team_set = set(teams)
    withdrawn: dict[str, int] = {}
    for item in raw_withdrawals:
        if not isinstance(item, dict):
            raise validation_error(["params.withdrawals"])
        team_id = item.get("team_id")
        after_round = item.get("after_round")
        if not isinstance(team_id, str) or team_id not in team_set:
            raise validation_error(["params.withdrawals"], "Unknown withdrawn team")
        if not is_int(after_round) or not 0 <= after_round <= round_count:
            raise validation_error(["params.withdrawals"], "after_round out of range")
        if team_id in withdrawn:
            raise validation_error(["params.withdrawals"], "Duplicate withdrawal")
        withdrawn[team_id] = after_round

    base = _base_rounds(teams)
    rounds_out: list[dict[str, Any]] = []
    summary = {"total": 0, "scheduled": 0, "forfeit": 0, "voided": 0}
    for leg in range(1, legs + 1):
        for r, (pairs, byes) in enumerate(base):
            number = (leg - 1) * per_leg + r + 1
            matches = []
            for index, (home, away) in enumerate(pairs, start=1):
                if leg == 2:
                    home, away = away, home
                status, awarded_to = "scheduled", None
                if policy == "void_all":
                    if home in withdrawn or away in withdrawn:
                        status = "voided"
                else:
                    home_out = home in withdrawn and number > withdrawn[home]
                    away_out = away in withdrawn and number > withdrawn[away]
                    if home_out and away_out:
                        status = "voided"
                    elif home_out:
                        status, awarded_to = "forfeit", away
                    elif away_out:
                        status, awarded_to = "forfeit", home
                summary["total"] += 1
                summary[status] += 1
                matches.append(
                    {
                        "match_id": f"RR-L{leg}-R{number}-M{index}",
                        "leg": leg,
                        "home": home,
                        "away": away,
                        "status": status,
                        "awarded_to": awarded_to,
                    }
                )
            rounds_out.append({"round": number, "matches": matches, "byes": list(byes)})

    return {
        "format": "round_robin",
        "legs": legs,
        "team_count": n,
        "round_count": round_count,
        "rounds": rounds_out,
        "summary": summary,
    }
