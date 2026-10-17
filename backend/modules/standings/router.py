"""League standings API."""

from typing import Any

from fastapi import APIRouter

from backend.core.db import SessionLocal
from backend.modules.standings.service import get_standings

router = APIRouter()


@router.get("/audit/v1/standings/{league_id}")
def standings(league_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        return get_standings(session, league_id)
