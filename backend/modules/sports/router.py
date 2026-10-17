"""Autograder and application routes for sport configuration."""

from typing import Any

from fastapi import APIRouter, Body

from backend.core.db import SessionLocal
from backend.modules.sports.service import create_sport

router = APIRouter()


@router.post("/audit/v1/sports", status_code=201)
def post_sport(body: Any = Body(...)) -> dict[str, Any]:
    with SessionLocal() as session:
        return create_sport(session, body)
