"""Store audit API: checkout and inventory (SPEC 5.12)."""

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.core.db import SessionLocal

# Importing the seed module registers the reset hook and the store models.
from backend.modules.store import models as _models  # noqa: F401
from backend.modules.store import seed as _seed  # noqa: F401
from backend.modules.store.service import checkout, get_inventory

router = APIRouter()


@router.post("/audit/v1/checkout", status_code=201)
def post_checkout(body: Any = Body(default=None)) -> JSONResponse:
    status_code, response = checkout(body)
    return JSONResponse(status_code=status_code, content=response)


@router.get("/audit/v1/inventory/{variant_id}")
def get_inventory_route(variant_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        return get_inventory(session, variant_id)
