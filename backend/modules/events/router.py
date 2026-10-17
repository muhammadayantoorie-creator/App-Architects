"""Match event ingestion endpoint."""

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.core.db import SessionLocal
from backend.core.redis_client import get_redis
from backend.modules.events.service import append_event, score_match

router = APIRouter()


def _publish_match_updated(channel: str) -> None:
    # Best effort: a realtime fan-out failure must never fail the committed event.
    try:
        client = get_redis()
        client.publish(channel, "match_updated")
    except Exception:
        pass


@router.post("/audit/v1/events", status_code=201)
def post_event(body: Any = Body(...)) -> JSONResponse:
    with SessionLocal() as session:
        with session.begin():
            result = append_event(session, body)

    if result.channel is not None:
        _publish_match_updated(result.channel)
    return JSONResponse(status_code=result.status_code, content=result.response)


@router.get("/audit/v1/score/{match_id}")
def get_score(match_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        return score_match(session, match_id)
