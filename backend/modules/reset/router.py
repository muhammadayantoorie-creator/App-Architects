"""Reset endpoint for the clean, repeatable grading baseline."""

from typing import Any

from fastapi import APIRouter, Body, Request
from sqlalchemy.orm import Session

from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.registry import clear_database, run_reset_hooks
from backend.core.state import baseline_is_seeded, set_value

# Importing the seed modules registers their ordered reset hooks and imports
# their models before metadata.create_all() runs at application startup.
from backend.modules.sports import seed as _sports_seed  # noqa: F401,E402
from backend.modules.tenants import seed as _tenants_seed  # noqa: F401,E402

router = APIRouter()

DEFAULT_SEED = 42
DEFAULT_STOCK = {"var-jersey-001-M": 1, "var-jersey-001-L": 5}
BASELINE_SPORT_IDS = ["football", "basketball", "cricket", "esports"]
BASELINE_TENANT_IDS = ["tenant-alpha", "tenant-beta"]


def _parse_reset_body(body: Any) -> tuple[int, dict[str, int]]:
    if not isinstance(body, dict):
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Reset body must be an object",
            {"fields": ["body"]},
        )

    fields: set[str] = set()
    seed = body.get("seed", DEFAULT_SEED)
    if not isinstance(seed, int) or isinstance(seed, bool):
        fields.add("seed")

    stock_in = body.get("stock", DEFAULT_STOCK)
    stock: dict[str, int] = {}
    if not isinstance(stock_in, dict):
        fields.add("stock")
    else:
        stock.update(DEFAULT_STOCK)
        for variant_id, quantity in stock_in.items():
            if not is_valid_id(variant_id):
                fields.add("stock")
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
                fields.add(f"stock.{variant_id}")
            elif is_valid_id(variant_id):
                stock[variant_id] = quantity

    if fields:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Reset configuration is invalid",
            {"fields": sorted(fields)},
        )
    return seed, stock


def reset_state(session: Session, body: Any) -> dict[str, Any]:
    seed, stock = _parse_reset_body(body)
    clear_database(session)
    run_reset_hooks(session, seed, stock)
    set_value(session, "last_reset_seed", str(seed))
    return {
        "status": "reset_complete",
        "seed": seed,
        "sports": BASELINE_SPORT_IDS,
        "tenants": BASELINE_TENANT_IDS,
        "stock": stock,
    }


@router.post("/audit/v1/reset")
def post_reset(
    request: Request, body: Any = Body(default={})
) -> dict[str, Any]:
    with SessionLocal.begin() as session:
        response = reset_state(session, body)
    with SessionLocal() as session:
        request.app.state.baseline_seeded = baseline_is_seeded(session)
    return response
