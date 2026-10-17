"""Validation, rules, and append-only writes for match events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.signing import canonical, salt, sign
from backend.modules.events.models import MatchEvent
from backend.modules.leagues.models import League, MatchStream
from backend.modules.sports.models import Sport

EVENT_KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
EVENT_TYPES = {
    "match_init",
    "match_start",
    "score",
    "discipline",
    "tiebreak_winner",
    "match_end",
    "compensation",
}


@dataclass(frozen=True)
class AppendResult:
    response: dict[str, Any]
    status_code: int
    channel: str | None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _schema(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Event body must be an object",
            {"fields": ["body"]},
        )

    fields: set[str] = set()
    event_id = body.get("event_id")
    match_id = body.get("match_id")
    event_type = body.get("type")
    payload = body.get("payload")

    if not is_valid_id(event_id):
        fields.add("event_id")
    if not is_valid_id(match_id):
        fields.add("match_id")
    if not isinstance(event_type, str):
        fields.add("type")
    if not isinstance(payload, dict):
        fields.add("payload")

    if isinstance(event_type, str) and isinstance(payload, dict):
        def required_id(field: str) -> None:
            if not is_valid_id(payload.get(field)):
                fields.add(f"payload.{field}")

        if event_type == "match_init":
            required_id("sport_id")
            required_id("home_team_id")
            required_id("away_team_id")
            if "league_id" in payload:
                required_id("league_id")
        elif event_type == "score":
            required_id("team_id")
            event_name = payload.get("event_type")
            if not isinstance(event_name, str) or not EVENT_KEY_RE.fullmatch(event_name):
                fields.add("payload.event_type")
        elif event_type in {"discipline", "tiebreak_winner"}:
            required_id("team_id")
            if event_type == "discipline" and not _is_int(payload.get("points")):
                fields.add("payload.points")
        elif event_type == "compensation":
            required_id("compensates")
            if not isinstance(payload.get("reason"), str):
                fields.add("payload.reason")

    if fields:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Event configuration is invalid",
            {"fields": sorted(fields)},
        )

    # Schema problems (400) win over missing references (404): an unknown
    # stream event type is rejected before the match is looked up.
    if event_type not in EVENT_TYPES:
        raise ApiError(
            400,
            "UNKNOWN_EVENT_TYPE",
            f"Unknown event type {event_type}.",
            {"type": event_type},
        )

    return {
        "event_id": event_id,
        "match_id": match_id,
        "type": event_type,
        "payload": payload,
        "request_body": canonical(body),
    }


def _lock(session: Session, scope: str, key: str) -> None:
    # The PostgreSQL transaction lock makes event-id replay and per-match
    # sequence assignment atomic across concurrent API requests.
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"{scope}:{key}"},
    )


def _api_error(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> ApiError:
    return ApiError(status, code, message, details or {})


def _not_found(code: str, name: str, value: str) -> ApiError:
    return _api_error(404, code, f"{name} {value} was not found.", {name: value})


def _events_for(session: Session, match_id: str) -> list[MatchEvent]:
    return list(
        session.scalars(
            select(MatchEvent)
            .where(MatchEvent.match_id == match_id)
            .order_by(MatchEvent.sequence)
        ).all()
    )


def _compensated_ids(events: list[MatchEvent]) -> set[str]:
    return {
        str(event.payload["compensates"])
        for event in events
        if event.event_type == "compensation"
    }


def _active_events(events: list[MatchEvent]) -> list[MatchEvent]:
    compensated = _compensated_ids(events)
    return [
        event
        for event in events
        if event.event_type != "compensation" and event.event_id not in compensated
    ]


def _status(events: list[MatchEvent]) -> str:
    status = "upcoming"
    for event in events:
        if event.event_type == "match_start":
            status = "in_progress"
        elif event.event_type == "match_end":
            status = "completed"
    return status


def _score_totals(
    events: list[MatchEvent], stream: MatchStream, sport: Sport
) -> dict[str, int]:
    totals = {stream.home_team_id: 0, stream.away_team_id: 0}
    model = sport.scoring_model
    score_field = {"event": "points", "innings": "runs", "round": "rounds"}[model]
    scoring_events = sport.config["scoring_events"]
    for event in _active_events(events):
        if event.event_type != "score":
            continue
        team_id = event.payload["team_id"]
        event_config = scoring_events[event.payload["event_type"]]
        totals[team_id] += event_config[score_field]
    return totals


def _check_model_limit(
    events: list[MatchEvent],
    sport: Sport,
    team_id: str,
) -> None:
    active = _active_events(events)
    periods = sport.config["periods"]

    if sport.scoring_model == "innings":
        legal_balls = 0
        wickets = 0
        for event in active:
            if event.event_type != "score" or event.payload["team_id"] != team_id:
                continue
            scoring = sport.config["scoring_events"][event.payload["event_type"]]
            legal_balls += int(scoring["legal_ball"])
            wickets += int(scoring["wicket"])
        ball_limit = (
            periods["innings_per_team"]
            * periods["overs_per_innings"]
            * periods["balls_per_over"]
        )
        wicket_limit = periods["innings_per_team"] * periods["wickets_per_innings"]
        if legal_balls >= ball_limit or wickets >= wicket_limit:
            raise _api_error(
                409,
                "INNINGS_COMPLETE",
                "The team has completed its innings.",
                {"team_id": team_id},
            )

    if sport.scoring_model == "round":
        rounds_won = sum(
            sport.config["scoring_events"][event.payload["event_type"]]["rounds"]
            for event in active
            if event.event_type == "score" and event.payload["team_id"] == team_id
        )
        required = (periods["best_of"] + 1) // 2
        if rounds_won >= required:
            raise _api_error(
                409,
                "SERIES_ALREADY_DECIDED",
                "The series has already been decided.",
                {"team_id": team_id},
            )


def _validate_type_rules(
    session: Session,
    config: dict[str, Any],
    stream: MatchStream,
    sport: Sport,
    events: list[MatchEvent],
) -> None:
    event_type = config["type"]
    payload = config["payload"]
    if event_type not in EVENT_TYPES:
        raise _api_error(400, "UNKNOWN_EVENT_TYPE", "Unknown event type")

    if event_type == "match_init":
        raise _api_error(
            409,
            "MATCH_EXISTS",
            f"Match {config['match_id']} already exists.",
            {"match_id": config["match_id"]},
        )

    if event_type == "score":
        team_id = payload["team_id"]
        if team_id not in {stream.home_team_id, stream.away_team_id}:
            raise _api_error(
                400,
                "VALIDATION_ERROR",
                "Scoring team must be a home or away team",
                {"fields": ["payload.team_id"]},
            )
        event_config = sport.config["scoring_events"].get(payload["event_type"])
        if event_config is None:
            raise _api_error(
                400,
                "UNKNOWN_EVENT_TYPE",
                f"Unknown scoring event {payload['event_type']}.",
                {"event_type": payload["event_type"]},
            )
        if _status(events) != "in_progress":
            raise _api_error(
                409,
                "MATCH_NOT_IN_PROGRESS",
                "The match is not in progress.",
                {"match_id": stream.match_id},
            )
        _check_model_limit(events, sport, team_id)
        return

    if event_type in {"discipline", "tiebreak_winner"}:
        team_id = payload["team_id"]
        if team_id not in {stream.home_team_id, stream.away_team_id}:
            raise _api_error(
                400,
                "VALIDATION_ERROR",
                "Event team must be a home or away team",
                {"fields": ["payload.team_id"]},
            )
        if _status(events) != "in_progress":
            raise _api_error(
                409,
                "MATCH_NOT_IN_PROGRESS",
                "The match is not in progress.",
                {"match_id": stream.match_id},
            )
        return

    status = _status(events)
    if event_type == "match_start":
        if status != "upcoming":
            raise _api_error(
                409,
                "ILLEGAL_TRANSITION",
                "Only an upcoming match can be started.",
                {"match_id": stream.match_id},
            )
        return

    if event_type == "match_end":
        if status != "in_progress":
            raise _api_error(
                409,
                "ILLEGAL_TRANSITION",
                "Only an in-progress match can be ended.",
                {"match_id": stream.match_id},
            )
        totals = _score_totals(events, stream, sport)
        has_tiebreak = any(
            event.event_type == "tiebreak_winner"
            for event in _active_events(events)
        )
        if (
            totals[stream.home_team_id] == totals[stream.away_team_id]
            and not stream.draw_allowed
            and not has_tiebreak
        ):
            raise _api_error(
                409,
                "TIE_NOT_ALLOWED",
                "A tied match requires an active tie-break winner.",
                {"match_id": stream.match_id},
            )
        return

    if event_type == "compensation":
        target_id = payload["compensates"]
        target = session.get(MatchEvent, target_id)
        if target is None:
            raise _not_found("EVENT_NOT_FOUND", "event_id", target_id)
        compensated = _compensated_ids(events)
        if (
            target.match_id != stream.match_id
            or target.event_type not in {"score", "discipline", "tiebreak_winner"}
            or target_id in compensated
        ):
            raise _api_error(
                409,
                "INVALID_COMPENSATION",
                "The event cannot be compensated.",
                {"event_id": target_id},
            )


def append_event(session: Session, body: Any) -> AppendResult:
    config = _schema(body)
    event_id = config["event_id"]
    match_id = config["match_id"]
    event_type = config["type"]
    payload = config["payload"]

    _lock(session, "event", event_id)
    existing_event = session.get(MatchEvent, event_id)
    if existing_event is not None:
        if existing_event.request_body == config["request_body"]:
            return AppendResult(existing_event.response_body, 200, None)
        raise _api_error(
            409,
            "DUPLICATE_EVENT_ID",
            f"Event id {event_id} was already used with a different body.",
            {"event_id": event_id},
        )

    _lock(session, "match", match_id)
    stream = session.get(MatchStream, match_id)

    if event_type == "match_init":
        # Validation order: 400 schema, then 404 references, then 409 conflicts.
        home = payload["home_team_id"]
        away = payload["away_team_id"]
        if home == away:
            raise _api_error(
                400,
                "VALIDATION_ERROR",
                "Home and away teams must differ",
                {"fields": ["payload.away_team_id"]},
            )
        sport_id = payload["sport_id"]
        sport = session.get(Sport, sport_id)
        if sport is None:
            raise _not_found("SPORT_NOT_FOUND", "sport_id", sport_id)
        league_id = payload.get("league_id")
        if league_id is not None and session.get(League, league_id) is None:
            raise _not_found("LEAGUE_NOT_FOUND", "league_id", league_id)
        if stream is not None:
            # A league fixture registers its stream without events; an init
            # that describes exactly that fixture opens its event log.
            adopts_fixture = (
                stream.version == 0
                and not _events_for(session, match_id)
                and stream.sport_id == sport.sport_id
                and stream.home_team_id == home
                and stream.away_team_id == away
                and (league_id is None or league_id == stream.league_id)
            )
            if not adopts_fixture:
                raise _api_error(
                    409,
                    "MATCH_EXISTS",
                    f"Match {match_id} already exists.",
                    {"match_id": match_id},
                )
        else:
            stream = MatchStream(
                match_id=match_id,
                sport_id=sport.sport_id,
                league_id=league_id,
                home_team_id=home,
                away_team_id=away,
                status="upcoming",
                version=0,
                draw_allowed=bool(sport.config["draw_allowed"]),
            )
            session.add(stream)
            session.flush()
        events: list[MatchEvent] = []
    else:
        if stream is None:
            raise _not_found("MATCH_NOT_FOUND", "match_id", match_id)
        sport = session.get(Sport, stream.sport_id)
        if sport is None:
            raise _not_found("SPORT_NOT_FOUND", "sport_id", stream.sport_id)
        events = _events_for(session, match_id)
        _validate_type_rules(session, config, stream, sport, events)

    sequence = len(events) + 1
    signature = sign(salt(), event_id, payload)
    response = {
        "event_id": event_id,
        "match_id": match_id,
        "type": event_type,
        "sequence": sequence,
        "match_version": sequence,
        "signature": signature,
    }
    session.add(
        MatchEvent(
            event_id=event_id,
            match_id=match_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            request_body=config["request_body"],
            response_body=response,
            signature=signature,
        )
    )
    # Keep the denormalised stream summary in step with the event log.
    stream.version = sequence
    if event_type == "match_start":
        stream.status = "in_progress"
    elif event_type == "match_end":
        stream.status = "completed"
    session.flush()
    return AppendResult(response, 201, f"live:{stream.league_id or stream.match_id}")


def score_match(session: Session, match_id: str) -> dict[str, Any]:
    """Rebuild the score projection from the immutable match event log."""
    stream = session.get(MatchStream, match_id)
    if stream is None:
        raise _not_found("MATCH_NOT_FOUND", "match_id", match_id)

    sport = session.get(Sport, stream.sport_id)
    if sport is None:
        raise _not_found("SPORT_NOT_FOUND", "sport_id", stream.sport_id)

    events = _events_for(session, match_id)
    active = _active_events(events)
    totals = _score_totals(events, stream, sport)
    home = {
        "team_id": stream.home_team_id,
        "score": totals[stream.home_team_id],
        "wickets": None,
        "balls": None,
        "overs": None,
        "fair_play": 0,
    }
    away = {
        "team_id": stream.away_team_id,
        "score": totals[stream.away_team_id],
        "wickets": None,
        "balls": None,
        "overs": None,
        "fair_play": 0,
    }

    wickets_by_team = {stream.home_team_id: 0, stream.away_team_id: 0}
    balls_by_team = {stream.home_team_id: 0, stream.away_team_id: 0}
    for event in active:
        team_id = event.payload.get("team_id")
        if event.event_type == "discipline" and team_id in {
            stream.home_team_id,
            stream.away_team_id,
        }:
            if team_id == stream.home_team_id:
                home["fair_play"] += event.payload["points"]
            elif team_id == stream.away_team_id:
                away["fair_play"] += event.payload["points"]
        elif (
            sport.scoring_model == "innings"
            and event.event_type == "score"
            and team_id in wickets_by_team
        ):
            scoring = sport.config["scoring_events"][event.payload["event_type"]]
            balls_by_team[team_id] += int(scoring["legal_ball"])
            wickets_by_team[team_id] += int(scoring["wicket"])

    if sport.scoring_model == "innings":
        balls_per_over = sport.config["periods"]["balls_per_over"]
        for row, team_id in ((home, stream.home_team_id), (away, stream.away_team_id)):
            balls = balls_by_team[team_id]
            row["balls"] = balls
            row["wickets"] = wickets_by_team[team_id]
            row["overs"] = f"{balls // balls_per_over}.{balls % balls_per_over}"

    active_tiebreaks = [
        event for event in active if event.event_type == "tiebreak_winner"
    ]
    tiebreak_winner = (
        active_tiebreaks[-1].payload["team_id"] if active_tiebreaks else None
    )
    if totals[stream.home_team_id] > totals[stream.away_team_id]:
        winner = stream.home_team_id
    elif totals[stream.away_team_id] > totals[stream.home_team_id]:
        winner = stream.away_team_id
    else:
        winner = tiebreak_winner

    status = _status(events)
    if status != "completed":
        outcome = "pending"
    elif winner is not None:
        outcome = "home_win" if winner == stream.home_team_id else "away_win"
    elif stream.draw_allowed:
        outcome = "draw"
    else:
        outcome = "undecided"

    compensated_by = {
        str(event.payload["compensates"]): event.event_id
        for event in events
        if event.event_type == "compensation"
    }
    projected_events = [
        {
            "sequence": event.sequence,
            "event_id": event.event_id,
            "type": event.event_type,
            "payload": event.payload,
            "signature": event.signature,
            "compensated": event.event_id in compensated_by,
            "compensated_by": compensated_by.get(event.event_id),
        }
        for event in events
    ]

    return {
        "match_id": stream.match_id,
        "sport_id": stream.sport_id,
        "league_id": stream.league_id,
        "status": status,
        "outcome": outcome,
        "winner_team_id": winner,
        "tiebreak_winner_team_id": tiebreak_winner,
        "home": home,
        "away": away,
        "version": len(events),
        "events": projected_events,
    }
