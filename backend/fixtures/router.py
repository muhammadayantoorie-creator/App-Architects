"""POST /audit/v1/fixtures — pure computation, stores nothing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from backend.core.ids import is_valid_id
from backend.fixtures import double_elim, round_robin, single_elim, swiss, validation_error

router = APIRouter()

LIMITS = {
    "round_robin": (2, 40),
    "swiss": (2, 64),
    "single_elim": (2, 128),
    "double_elim": (3, 128),
}
GENERATORS = {
    "round_robin": round_robin.generate,
    "swiss": swiss.generate,
    "single_elim": single_elim.generate,
    "double_elim": double_elim.generate,
}


def build_fixtures(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise validation_error(["body"])
    fmt = body.get("format")
    if not isinstance(fmt, str) or fmt not in LIMITS:
        raise validation_error(["format"])
    teams = body.get("teams")
    if not isinstance(teams, list) or not all(is_valid_id(t) for t in teams):
        raise validation_error(["teams"])
    if len(set(teams)) != len(teams):
        raise validation_error(["teams"], "Team ids must be unique")
    low, high = LIMITS[fmt]
    if not low <= len(teams) <= high:
        raise validation_error(["teams"], f"{fmt} requires {low}-{high} teams")
    params = body.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise validation_error(["params"])
    return GENERATORS[fmt](list(teams), params)


@router.post("/audit/v1/fixtures")
def post_fixtures(body: Any = Body(...)) -> dict[str, Any]:
    return build_fixtures(body)
