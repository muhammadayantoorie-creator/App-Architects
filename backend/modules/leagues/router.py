"""League setup API."""

from typing import Any

from fastapi import APIRouter, Body

from backend.core.db import SessionLocal
from backend.modules.leagues.service import create_league

router = APIRouter()


@router.post("/audit/v1/leagues", status_code=201)
def post_league(body: Any = Body(...)) -> dict[str, Any]:
    with SessionLocal.begin() as session:
        return create_league(session, body)
