"""POST /audit/v1/offline-sync."""

from typing import Any

from fastapi import APIRouter, Body

from backend.modules.offline_sync import models as _models  # noqa: F401
from backend.modules.offline_sync.service import process_offline_sync

router = APIRouter()


@router.post("/audit/v1/offline-sync")
def post_offline_sync(body: Any = Body(...)) -> dict[str, Any]:
    return process_offline_sync(body)
