"""Roster audit endpoints: setup, transfer/loan/release, history."""

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.core.db import SessionLocal
from backend.modules.roster import models as _models  # noqa: F401
from backend.modules.roster import seed as _seed  # noqa: F401
from backend.modules.roster.service import player_history, setup_roster, transfer

router = APIRouter()


@router.post("/audit/v1/roster/setup", status_code=201)
def post_roster_setup(body: Any = Body(...)) -> dict[str, Any]:
    with SessionLocal.begin() as session:
        return setup_roster(session, body)


@router.post("/audit/v1/roster/transfer", status_code=201)
def post_roster_transfer(body: Any = Body(...)) -> JSONResponse:
    status_code, response = transfer(None, body)
    return JSONResponse(status_code=status_code, content=response)


@router.get("/audit/v1/roster/history/{player_id}")
def get_roster_history(player_id: str, as_of: str | None = None) -> dict[str, Any]:
    with SessionLocal.begin() as session:
        return player_history(session, player_id, as_of)
