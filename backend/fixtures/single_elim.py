"""Single elimination bracket with exact recursive seeding."""

from __future__ import annotations

from typing import Any

from backend.fixtures import Bracket, get_bool, next_pow2, seed_first_round


def generate(teams: list[str], params: dict[str, Any]) -> dict[str, Any]:
    third_place = get_bool(params, "third_place_match", False)
    n = len(teams)
    size = next_pow2(n)
    rounds = size.bit_length() - 1
    bracket = Bracket({team: i + 1 for i, team in enumerate(teams)})

    for r in range(1, rounds + 1):
        for i in range(1, (size >> r) + 1):
            bracket.add(f"R{r}M{i}", "main", r, i)
    seed_first_round(bracket, teams, size, "R")
    for r in range(1, rounds):
        for i in range(1, (size >> r) + 1):
            bracket.link(f"R{r}M{i}", "winner", f"R{r + 1}M{(i + 1) // 2}", "home" if i % 2 else "away")

    if third_place and rounds >= 2:
        bracket.add("TP", "third_place", rounds, 1)
        bracket.link(f"R{rounds - 1}M1", "loser", "TP", "home")
        bracket.link(f"R{rounds - 1}M2", "loser", "TP", "away")

    bracket.resolve(bracket.parse_results(params))

    out_rounds = []
    for r in range(1, rounds + 1):
        out_rounds.append(
            {
                "round": r,
                "matches": [bracket.render(m) for m in bracket.sequence if m["round"] == r],
            }
        )
    return {"format": "single_elim", "bracket_size": size, "rounds": out_rounds}
