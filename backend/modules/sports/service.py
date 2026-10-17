"""Validation and creation of data-driven sport definitions."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.errors import ApiError
from backend.modules.sports.models import Sport

SPORT_ID_RE = re.compile(r"^[a-z0-9_-]{2,40}$")
EVENT_KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
FULL_TIE_BREAK_ORDER = [
    "h2h_points",
    "h2h_diff",
    "overall_diff",
    "scored",
    "fair_play",
    "draw_lots",
]
TIE_BREAKS = set(FULL_TIE_BREAK_ORDER)
OVERTIME_POLICIES = {"none", "extra_time", "shootout", "golden_score", "super_over"}


def _is_int(value: Any, minimum: int | None = None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (minimum is None or value >= minimum)
    )


def _dict(value: Any) -> bool:
    return isinstance(value, dict)


def _validate_config(body: Any) -> dict[str, Any]:
    fields: set[str] = set()
    if not _dict(body):
        raise ApiError(400, "VALIDATION_ERROR", "Request body must be an object", {"fields": ["body"]})

    sport_id = body.get("sport_id")
    name = body.get("name")
    scoring_model = body.get("scoring_model")
    if not isinstance(sport_id, str) or not SPORT_ID_RE.fullmatch(sport_id):
        fields.add("sport_id")
    if not isinstance(name, str) or not 1 <= len(name) <= 80:
        fields.add("name")
    if not isinstance(scoring_model, str) or scoring_model not in {
        "event",
        "innings",
        "round",
    }:
        fields.add("scoring_model")
        scoring_model = None

    periods = body.get("periods")
    periods_out: dict[str, int] = {}
    period_rules = {
        "event": {"count": 1, "duration_minutes": 1},
        "innings": {
            "innings_per_team": 1,
            "overs_per_innings": 1,
            "balls_per_over": 1,
            "wickets_per_innings": 1,
        },
        "round": {"best_of": 1},
    }
    if not _dict(periods):
        fields.add("periods")
    elif scoring_model in period_rules:
        for key, minimum in period_rules[scoring_model].items():
            value = periods.get(key)
            valid = _is_int(value, minimum)
            if key == "best_of" and valid:
                valid = value % 2 == 1
            if not valid:
                fields.add(f"periods.{key}")
            else:
                periods_out[key] = value

    scoring_events = body.get("scoring_events")
    events_out: dict[str, dict[str, Any]] = {}
    if not _dict(scoring_events) or not scoring_events:
        fields.add("scoring_events")
    elif scoring_model in {"event", "innings", "round"}:
        for event_name, event_config in scoring_events.items():
            key_valid = isinstance(event_name, str) and EVENT_KEY_RE.fullmatch(event_name)
            if not key_valid:
                fields.add("scoring_events")
                continue
            if not _dict(event_config):
                fields.add(f"scoring_events.{event_name}")
                continue
            if scoring_model == "event":
                points = event_config.get("points")
                if not _is_int(points, 1):
                    fields.add(f"scoring_events.{event_name}.points")
                else:
                    events_out[event_name] = {"points": points}
            elif scoring_model == "innings":
                runs = event_config.get("runs")
                legal_ball = event_config.get("legal_ball")
                wicket = event_config.get("wicket")
                if not _is_int(runs, 0):
                    fields.add(f"scoring_events.{event_name}.runs")
                if not isinstance(legal_ball, bool):
                    fields.add(f"scoring_events.{event_name}.legal_ball")
                if not isinstance(wicket, bool):
                    fields.add(f"scoring_events.{event_name}.wicket")
                if (
                    _is_int(runs, 0)
                    and isinstance(legal_ball, bool)
                    and isinstance(wicket, bool)
                ):
                    events_out[event_name] = {
                        "runs": runs,
                        "legal_ball": legal_ball,
                        "wicket": wicket,
                    }
            else:
                rounds = event_config.get("rounds")
                if not _is_int(rounds, 1):
                    fields.add(f"scoring_events.{event_name}.rounds")
                else:
                    events_out[event_name] = {"rounds": rounds}

    draw_allowed = body.get("draw_allowed")
    if not isinstance(draw_allowed, bool):
        fields.add("draw_allowed")

    overtime = body.get("overtime")
    overtime_out: dict[str, Any] = {}
    if not _dict(overtime):
        fields.add("overtime")
    else:
        policy = overtime.get("policy")
        if not isinstance(policy, str) or policy not in OVERTIME_POLICIES:
            fields.add("overtime.policy")
        else:
            overtime_out["policy"] = policy
        if "duration_minutes" in overtime:
            duration = overtime["duration_minutes"]
            if not _is_int(duration, 0):
                fields.add("overtime.duration_minutes")
            else:
                overtime_out["duration_minutes"] = duration

    tie_order = body.get("tie_break_order", FULL_TIE_BREAK_ORDER)
    if not isinstance(tie_order, list):
        fields.add("tie_break_order")
        tie_order_out = FULL_TIE_BREAK_ORDER.copy()
    else:
        seen: set[str] = set()
        tie_order_out = []
        for index, item in enumerate(tie_order):
            if not isinstance(item, str) or item not in TIE_BREAKS or item in seen:
                fields.add(f"tie_break_order.{index}")
                continue
            seen.add(item)
            if item != "draw_lots":
                tie_order_out.append(item)
        tie_order_out.append("draw_lots")

    roster = body.get("roster")
    roster_out: dict[str, Any] = {}
    if not _dict(roster):
        fields.add("roster")
    else:
        minimum = roster.get("min_squad_size")
        maximum = roster.get("max_squad_size")
        positions = roster.get("required_positions")
        if not _is_int(minimum, 1):
            fields.add("roster.min_squad_size")
        if not _is_int(maximum, 1):
            fields.add("roster.max_squad_size")
        if _is_int(minimum, 1) and _is_int(maximum, 1) and minimum > maximum:
            fields.update(("roster.min_squad_size", "roster.max_squad_size"))
        if not _dict(positions):
            fields.add("roster.required_positions")
        else:
            positions_out: dict[str, int] = {}
            for position, count in positions.items():
                if not isinstance(position, str) or not position:
                    fields.add("roster.required_positions")
                elif not _is_int(count, 0):
                    fields.add(f"roster.required_positions.{position}")
                else:
                    positions_out[position] = count
            roster_out["required_positions"] = positions_out
        if _is_int(minimum, 1):
            roster_out["min_squad_size"] = minimum
        if _is_int(maximum, 1):
            roster_out["max_squad_size"] = maximum

    if fields:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Sport configuration is invalid",
            {"fields": sorted(fields)},
        )

    return {
        "sport_id": sport_id,
        "name": name,
        "scoring_model": scoring_model,
        "periods": periods_out,
        "scoring_events": events_out,
        "draw_allowed": draw_allowed,
        "overtime": overtime_out,
        "tie_break_order": tie_order_out,
        "roster": roster_out,
    }


def create_sport(session: Session, body: Any) -> dict[str, Any]:
    config = _validate_config(body)
    existing = session.get(Sport, config["sport_id"])
    if existing is not None:
        raise ApiError(409, "SPORT_EXISTS", "Sport id already exists")

    sport = Sport(
        sport_id=config["sport_id"],
        name=config["name"],
        scoring_model=config["scoring_model"],
        config=config,
    )
    session.add(sport)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "SPORT_EXISTS", "Sport id already exists") from exc
    return {"sport_id": sport.sport_id, "status": "created", "config": config}
