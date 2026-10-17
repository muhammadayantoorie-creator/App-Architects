"""Double elimination bracket: winners, losers and grand final (optional reset)."""

from __future__ import annotations

from typing import Any

from backend.fixtures import Bracket, get_bool, next_pow2, seed_first_round


def _losers_count(size: int, r: int) -> int:
    j = (r + 1) // 2
    return size >> (j + 1)


def generate(teams: list[str], params: dict[str, Any]) -> dict[str, Any]:
    reset = get_bool(params, "bracket_reset", True)
    n = len(teams)
    size = next_pow2(n)
    k = size.bit_length() - 1
    lb_rounds = 2 * (k - 1)
    bracket = Bracket({team: i + 1 for i, team in enumerate(teams)})

    for r in range(1, k + 1):
        for i in range(1, (size >> r) + 1):
            bracket.add(f"WR{r}M{i}", "winners", r, i)
    for r in range(1, lb_rounds + 1):
        for i in range(1, _losers_count(size, r) + 1):
            bracket.add(f"LR{r}M{i}", "losers", r, i)
    gf1 = bracket.add("GF1", "grand_final", 1, 1)
    gf2 = bracket.add("GF2", "grand_final", 2, 1) if reset else None

    seed_first_round(bracket, teams, size, "WR")

    def parity(i: int) -> str:
        return "home" if i % 2 else "away"

    # Winners bracket.
    for r in range(1, k + 1):
        for i in range(1, (size >> r) + 1):
            mid = f"WR{r}M{i}"
            if r < k:
                bracket.link(mid, "winner", f"WR{r + 1}M{(i + 1) // 2}", parity(i))
            else:
                bracket.link(mid, "winner", "GF1", "home")
            if r == 1:
                bracket.link(mid, "loser", f"LR1M{(i + 1) // 2}", parity(i))
            else:
                bracket.link(mid, "loser", f"LR{2 * r - 2}M{i}", "away")
    # Losers bracket.
    for r in range(1, lb_rounds + 1):
        for i in range(1, _losers_count(size, r) + 1):
            mid = f"LR{r}M{i}"
            if r == lb_rounds:
                bracket.link(mid, "winner", "GF1", "away")
            elif r % 2 == 1:
                bracket.link(mid, "winner", f"LR{r + 1}M{i}", "home")
            else:
                bracket.link(mid, "winner", f"LR{r + 1}M{(i + 1) // 2}", parity(i))
    # Grand final.
    if gf2 is not None:
        bracket.link("GF1", "winner", "GF2", "home")
        bracket.link("GF1", "loser", "GF2", "away")
        gf2["gate"] = lambda: gf1["winner"] is not None and gf1["winner"] == gf1["away"]

    bracket.resolve(bracket.parse_results(params))

    def rounds_of(prefix: str, count: int) -> list[dict[str, Any]]:
        return [
            {
                "round": r,
                "matches": [
                    bracket.render(m)
                    for m in bracket.sequence
                    if m["match_id"].startswith(f"{prefix}{r}M")
                ],
            }
            for r in range(1, count + 1)
        ]

    grand_final = [bracket.render(gf1)]
    if gf2 is not None:
        out = bracket.render(gf2)
        gf1_winner = bracket.team(gf1["winner"])
        if gf1_winner is None:
            # Same two teams as GF1 until GF1 is decided.
            out["home"], out["away"] = bracket.team(gf1["home"]), bracket.team(gf1["away"])
            out["home_seed"], out["away_seed"] = bracket.seed(gf1["home"]), bracket.seed(gf1["away"])
            required = None
        else:
            required = bool(reset and gf1_winner == bracket.team(gf1["away"]))
        out["conditional"] = True
        out["required"] = required
        grand_final.append(out)

    return {
        "format": "double_elim",
        "bracket_size": size,
        "bracket_reset": reset,
        "winners": rounds_of("WR", k),
        "losers": rounds_of("LR", lb_rounds),
        "grand_final": grand_final,
    }
