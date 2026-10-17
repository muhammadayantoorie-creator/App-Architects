"""Offline action replay (SPEC 5.14): ordered by queued_at, one transaction per action."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.redis_client import get_redis
from backend.core.signing import canonical
from backend.core.time import now_iso
from backend.modules.events.models import MatchEvent
from backend.modules.events.service import _schema as event_schema
from backend.modules.events.service import append_event
from backend.modules.leagues.models import MatchStream
from backend.modules.offline_sync.models import OfflineSyncAction
from backend.modules.roster import service as roster

ACTION_TYPES = {"score_event", "roster_transfer"}
QUEUED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_ACTIONS = 100


class _Outcome(Exception):
    """Raised inside an action transaction to roll it back and report a result."""

    def __init__(self, status: str, resolution: str, error_code: str | None, server_version: int) -> None:
        super().__init__(error_code or status)
        self.status = status
        self.resolution = resolution
        self.error_code = error_code
        self.server_version = server_version


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_queued_at(value: Any) -> bool:
    if not isinstance(value, str) or not QUEUED_AT_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def validate_envelope(body: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(body, dict):
        raise ApiError(400, "VALIDATION_ERROR", "Body must be an object", {"fields": ["body"]})
    fields: set[str] = set()
    device_id = body.get("device_id")
    if not is_valid_id(device_id):
        fields.add("device_id")
    actions = body.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        fields.add("actions")
    else:
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                fields.add(f"actions.{i}")
                continue
            if not is_valid_id(action.get("action_id")):
                fields.add(f"actions.{i}.action_id")
            if action.get("type") not in ACTION_TYPES:
                fields.add(f"actions.{i}.type")
            if not _valid_queued_at(action.get("queued_at")):
                fields.add(f"actions.{i}.queued_at")
            base = action.get("base_version")
            if not _is_int(base) or base < 0:
                fields.add(f"actions.{i}.base_version")
            if not isinstance(action.get("payload"), dict):
                fields.add(f"actions.{i}.payload")
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "Offline sync envelope is invalid", {"fields": sorted(fields)})
    return device_id, actions


# ---------------------------------------------------------------- versions


def _match_version(session: Session, match_id: Any) -> int:
    if not is_valid_id(match_id):
        return 0
    return int(
        session.scalar(
            select(func.count()).select_from(MatchEvent).where(MatchEvent.match_id == match_id)
        )
        or 0
    )


def _player_version(session: Session, payload: dict[str, Any]) -> int:
    league_id, player_id = payload.get("league_id"), payload.get("player_id")
    if not is_valid_id(league_id) or not is_valid_id(player_id):
        return 0
    return roster.audit_count(session, league_id, player_id)


def _current_version(session: Session, action: dict[str, Any]) -> int:
    payload = action["payload"]
    if action["type"] == "score_event":
        return _match_version(session, payload.get("match_id"))
    return _player_version(session, payload)


# ---------------------------------------------------------------- handlers


def _same_event(existing: MatchEvent, payload: dict[str, Any]) -> bool:
    if existing.request_body == canonical(payload):
        return True
    return (
        existing.match_id == payload.get("match_id")
        and existing.event_type == payload.get("type")
        and existing.payload == payload.get("payload")
    )


def _score_event(session: Session, action: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    payload = action["payload"]
    base = action["base_version"]
    event_id = payload.get("event_id")
    if is_valid_id(event_id):
        existing = session.get(MatchEvent, event_id)
        if existing is not None and _same_event(existing, payload):
            raise _Outcome("duplicate", "skipped_duplicate", None, _match_version(session, existing.match_id))

    try:
        event_schema(payload)
    except ApiError as exc:
        raise _Outcome("rejected", "server_wins", exc.code, _match_version(session, payload.get("match_id")))

    match_id = payload["match_id"]
    stream = session.get(MatchStream, match_id)
    if stream is None and payload.get("type") != "match_init":
        raise _Outcome("rejected", "server_wins", "MATCH_NOT_FOUND", 0)
    current = _match_version(session, match_id)
    if base > current:
        raise _Outcome("rejected", "server_wins", "INVALID_BASE_VERSION", current)

    try:
        result = append_event(session, payload)
    except ApiError as exc:
        raise _Outcome("rejected", "server_wins", exc.code, current)
    if result.status_code == 200:
        raise _Outcome("duplicate", "skipped_duplicate", None, current)

    return (
        {
            "status": "applied",
            "resolution": "appended" if base == current else "rebased_append",
            "error_code": None,
            "server_version": int(result.response["match_version"]),
            "signature": result.response["signature"],
        },
        result.channel,
    )


def _roster_transfer(session: Session, action: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    payload = action["payload"]
    base = action["base_version"]
    try:
        req = roster.parse_transfer(payload)
    except ApiError as exc:
        raise _Outcome("rejected", "server_wins", exc.code, _player_version(session, payload))

    roster._lock(session)
    stored = roster.find_stored_request(session, req)
    if stored is not None:
        current = _player_version(session, payload)
        if stored.request_hash == req.body_hash:
            raise _Outcome("duplicate", "skipped_duplicate", None, current)
        raise _Outcome("rejected", "server_wins", "VALIDATION_ERROR", current)

    try:
        ctx = roster.resolve_transfer(session, req)
    except ApiError as exc:
        raise _Outcome("rejected", "server_wins", exc.code, _player_version(session, payload))

    current = roster.audit_count(session, req.league_id, req.player_id)
    if base > current:
        raise _Outcome("rejected", "server_wins", "INVALID_BASE_VERSION", current)

    try:
        roster.apply_transfer(session, req, ctx)
    except ApiError as exc:
        raise _Outcome("rejected", "server_wins", exc.code, current)

    return (
        {
            "status": "applied",
            "resolution": "appended" if base == current else "rebased_append",
            "error_code": None,
            "server_version": roster.audit_count(session, req.league_id, req.player_id),
            "signature": None,
        },
        None,
    )


HANDLERS = {"score_event": _score_event, "roster_transfer": _roster_transfer}


def _publish(channel: str | None) -> None:
    if channel is None:
        return
    try:
        get_redis().publish(channel, "match_updated")
    except Exception:
        pass


def _record(session: Session, device_id: str, action: dict[str, Any], result: dict[str, Any]) -> None:
    session.add(
        OfflineSyncAction(
            device_id=device_id,
            action_id=action["action_id"],
            action_type=action["type"],
            result=result,
            processed_at=now_iso(),
        )
    )


def _process_action(device_id: str, action: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        if session.get(OfflineSyncAction, (device_id, action["action_id"])) is not None:
            return {
                "status": "duplicate",
                "resolution": "skipped_duplicate",
                "error_code": None,
                "server_version": _current_version(session, action),
                "signature": None,
            }

    channel = None
    try:
        with SessionLocal.begin() as session:
            result, channel = HANDLERS[action["type"]](session, action)
            _record(session, device_id, action, result)
    except _Outcome as outcome:
        result = {
            "status": outcome.status,
            "resolution": outcome.resolution,
            "error_code": outcome.error_code,
            "server_version": outcome.server_version,
            "signature": None,
        }
        try:
            with SessionLocal.begin() as session:
                _record(session, device_id, action, result)
        except Exception:
            pass
    except Exception:
        # Never fail the whole batch; the action can be retried later.
        with SessionLocal() as session:
            version = _current_version(session, action)
        return {
            "status": "rejected",
            "resolution": "server_wins",
            "error_code": "INTERNAL_ERROR",
            "server_version": version,
            "signature": None,
        }
    _publish(channel)
    return result


def process_offline_sync(body: Any) -> dict[str, Any]:
    device_id, actions = validate_envelope(body)
    order = sorted(range(len(actions)), key=lambda i: (actions[i]["queued_at"], i))
    results: list[dict[str, Any] | None] = [None] * len(actions)
    for position, index in enumerate(order, start=1):
        action = actions[index]
        outcome = _process_action(device_id, action)
        results[index] = {
            "action_id": action["action_id"],
            "status": outcome["status"],
            "resolution": outcome["resolution"],
            "error_code": outcome["error_code"],
            "processed_order": position,
            "server_version": outcome["server_version"],
            "signature": outcome["signature"],
        }
    summary = {"applied": 0, "rejected": 0, "duplicate": 0}
    for result in results:
        summary[result["status"]] += 1  # type: ignore[index]
    return {"device_id": device_id, "results": results, "summary": summary}
