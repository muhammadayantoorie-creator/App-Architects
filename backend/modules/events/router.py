"""Match event ingestion endpoint."""

import os
from typing import Any

import redis
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.core.db import SessionLocal
from backend.modules.events.service import append_event

router = APIRouter()


def _publish_match_updated(channel: str) -> None:
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_timeout=1,
    )
    try:
        client.publish(channel, "match_updated")
    finally:
        client.close()


@router.post("/audit/v1/events", status_code=201)
def post_event(body: Any = Body(...)) -> JSONResponse:
    with SessionLocal() as session:
        with session.begin():
            result = append_event(session, body)

    if result.channel is not None:
        _publish_match_updated(result.channel)
    return JSONResponse(status_code=result.status_code, content=result.response)
