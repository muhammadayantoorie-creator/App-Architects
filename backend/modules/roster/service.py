"""Roster setup, registration moves (transfer / loan / release) and history."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.signing import canonical
from backend.core.time import now_iso
from backend.modules.roster.models import (
    AuditEntry,
    RosterInMatch,
    RosterLeague,
    RosterPlayer,
    RosterRequest,
    Squad,
)
from backend.modules.sports.models import Sport

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROLES = {"captain", "vice_captain", "starter", "substitute"}
MOVE_TYPES = {"transfer", "loan", "release"}
STATE_ACTIVE = "active"
STATE_DEFERRED = "deferred_until_match_end"


# ---------------------------------------------------------------- helpers


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _validation(fields: set[str] | list[str], message: str) -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, {"fields": sorted(set(fields))})


def _not_found(code: str, field: str, value: Any) -> ApiError:
    return ApiError(404, code, f"{field} {value} was not found.", {field: value})


def _conflict(code: str, message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(409, code, message, details or {})


def _lock(session: Session, key: str = "roster") -> None:
    # Serialises roster writes (global audit counter, loan auto-return) on PostgreSQL.
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"roster:{key}"},
    )


def _audit_dict(entry: AuditEntry) -> dict[str, Any]:
    return {
        "audit_id": entry.audit_id,
        "action": entry.action,
        "player_id": entry.player_id,
        "league_id": entry.league_id,
        "from_squad_id": entry.from_squad_id,
        "to_squad_id": entry.to_squad_id,
        "effective_date": entry.effective_date,
        "state": entry.state,
        "who": entry.who,
        "when": entry.when_at,
        "why": entry.why,
    }


def _next_seq(session: Session) -> int:
    current = session.scalar(select(func.max(AuditEntry.seq)))
    return int(current or 0) + 1


def _append_audit(
    session: Session,
    *,
    league_id: str,
    player_id: str,
    action: str,
    from_squad_id: str | None,
    to_squad_id: str | None,
    effective_date: str,
    state: str,
    who: str | None,
    why: str | None,
) -> AuditEntry:
    seq = _next_seq(session)
    entry = AuditEntry(
        audit_id=f"au-{seq:04d}",
        seq=seq,
        league_id=league_id,
        player_id=player_id,
        action=action,
        from_squad_id=from_squad_id,
        to_squad_id=to_squad_id,
        effective_date=effective_date,
        state=state,
        who=who,
        when_at=now_iso(),
        why=why,
    )
    session.add(entry)
    session.flush()
    return entry


def audit_count(session: Session, league_id: str, player_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(AuditEntry)
            .where(AuditEntry.league_id == league_id, AuditEntry.player_id == player_id)
        )
        or 0
    )


def _get_player(session: Session, league_id: str, player_id: str) -> RosterPlayer | None:
    return session.scalars(
        select(RosterPlayer).where(
            RosterPlayer.league_id == league_id, RosterPlayer.player_id == player_id
        )
    ).first()


def _latest_player(session: Session, player_id: str) -> RosterPlayer | None:
    return session.scalars(
        select(RosterPlayer)
        .where(RosterPlayer.player_id == player_id)
        .order_by(RosterPlayer.id.desc())
    ).first()


def _get_squad(session: Session, league_id: str, squad_id: str) -> Squad | None:
    squad = session.scalars(
        select(Squad).where(Squad.league_id == league_id, Squad.squad_id == squad_id)
    ).first()
    if squad is None:
        # A squad registered under another league still "exists" (so a foreign
        # tenant's squad is reported as CROSS_TENANT_TRANSFER, not 404).
        squad = session.scalars(
            select(Squad).where(Squad.squad_id == squad_id).order_by(Squad.id.desc())
        ).first()
    return squad


def _squad_count(session: Session, league_id: str, squad_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(RosterPlayer)
            .where(
                RosterPlayer.league_id == league_id,
                RosterPlayer.squad_id == squad_id,
                RosterPlayer.released.is_(False),
            )
        )
        or 0
    )


def _position_count(session: Session, league_id: str, squad_id: str, position: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(RosterPlayer)
            .where(
                RosterPlayer.league_id == league_id,
                RosterPlayer.squad_id == squad_id,
                RosterPlayer.position == position,
                RosterPlayer.released.is_(False),
            )
        )
        or 0
    )


def _return_loan_if_expired(session: Session, player: RosterPlayer, as_of: date) -> bool:
    """Write the single loan_return entry once the loan has ended as of `as_of`."""
    if player.parent_squad_id is None or player.loan_end_date is None:
        return False
    loan_end = parse_date(player.loan_end_date)
    if loan_end is None or as_of <= loan_end:
        return False
    lender = player.parent_squad_id
    borrower = player.squad_id
    _append_audit(
        session,
        league_id=player.league_id,
        player_id=player.player_id,
        action="loan_return",
        from_squad_id=borrower,
        to_squad_id=lender,
        effective_date=(loan_end + timedelta(days=1)).isoformat(),
        state=STATE_ACTIVE,
        who="system",
        why="Loan ended",
    )
    player.squad_id = lender
    player.parent_squad_id = None
    player.loan_end_date = None
    player.role = "substitute"
    session.flush()
    return True


# ---------------------------------------------------------------- setup


def _sport_roster_defaults(sport: Sport) -> tuple[int | None, dict[str, int]]:
    roster = (sport.config or {}).get("roster") or {}
    max_size = roster.get("max_squad_size")
    required = roster.get("required_positions") or {}
    return (max_size if _is_int(max_size) else None), dict(required)


def setup_roster(session: Session, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _validation(["body"], "Roster setup body must be an object")

    fields: set[str] = set()
    league = body.get("league")
    window_open = window_close = None
    if not isinstance(league, dict):
        fields.add("league")
        league = {}
    else:
        for key in ("league_id", "tenant_id", "sport_id"):
            if not is_valid_id(league.get(key)):
                fields.add(f"league.{key}")
        window = league.get("transfer_window")
        if not isinstance(window, dict):
            fields.add("league.transfer_window")
        else:
            window_open = parse_date(window.get("open"))
            window_close = parse_date(window.get("close"))
            if window_open is None:
                fields.add("league.transfer_window.open")
            if window_close is None:
                fields.add("league.transfer_window.close")
            if window_open and window_close and window_open > window_close:
                fields.add("league.transfer_window")
        max_size = league.get("max_squad_size")
        if max_size is not None and (not _is_int(max_size) or max_size < 1):
            fields.add("league.max_squad_size")
        required = league.get("required_positions")
        if required is not None:
            if not isinstance(required, dict) or any(
                not isinstance(k, str) or not k or not _is_int(v) or v < 0
                for k, v in required.items()
            ):
                fields.add("league.required_positions")

    squads_in = body.get("squads", [])
    squads: list[dict[str, Any]] = []
    if not isinstance(squads_in, list):
        fields.add("squads")
    else:
        seen: set[str] = set()
        for i, squad in enumerate(squads_in):
            if not isinstance(squad, dict):
                fields.add(f"squads.{i}")
                continue
            squad_id = squad.get("squad_id")
            if not is_valid_id(squad_id):
                fields.add(f"squads.{i}.squad_id")
            elif squad_id in seen:
                fields.add(f"squads.{i}.squad_id")
            else:
                seen.add(squad_id)
            tenant_id = squad.get("tenant_id", league.get("tenant_id"))
            if not is_valid_id(tenant_id):
                fields.add(f"squads.{i}.tenant_id")
            club_id = squad.get("club_id")
            if club_id is not None and not is_valid_id(club_id):
                fields.add(f"squads.{i}.club_id")
            name = squad.get("name", squad_id)
            if not isinstance(name, str) or not name:
                fields.add(f"squads.{i}.name")
            squads.append(
                {"squad_id": squad_id, "tenant_id": tenant_id, "club_id": club_id, "name": name}
            )

    players_in = body.get("players", [])
    players: list[dict[str, Any]] = []
    if not isinstance(players_in, list):
        fields.add("players")
    else:
        seen_players: set[str] = set()
        for i, player in enumerate(players_in):
            if not isinstance(player, dict):
                fields.add(f"players.{i}")
                continue
            player_id = player.get("player_id")
            if not is_valid_id(player_id) or player_id in seen_players:
                fields.add(f"players.{i}.player_id")
            else:
                seen_players.add(player_id)
            name = player.get("name", player_id)
            if not isinstance(name, str) or not name:
                fields.add(f"players.{i}.name")
            position = player.get("position")
            if not isinstance(position, str) or not position or len(position) > 64:
                fields.add(f"players.{i}.position")
            squad_id = player.get("squad_id")
            if squad_id is not None and not is_valid_id(squad_id):
                fields.add(f"players.{i}.squad_id")
            role = player.get("role", "substitute")
            if role not in ROLES:
                fields.add(f"players.{i}.role")
            players.append(
                {
                    "player_id": player_id,
                    "name": name,
                    "position": position,
                    "squad_id": squad_id,
                    "role": role,
                }
            )

    matches_in = body.get("matches_in_progress", [])
    if matches_in is None:
        matches_in = []
    matches: list[dict[str, Any]] = []
    if not isinstance(matches_in, list):
        fields.add("matches_in_progress")
    else:
        for i, match in enumerate(matches_in):
            if not isinstance(match, dict):
                fields.add(f"matches_in_progress.{i}")
                continue
            for key in ("match_id", "home_squad_id", "away_squad_id"):
                if not is_valid_id(match.get(key)):
                    fields.add(f"matches_in_progress.{i}.{key}")
            matches.append(match)

    if fields:
        raise _validation(fields, "Roster setup is invalid")

    league_id = league["league_id"]
    sport = session.get(Sport, league["sport_id"])
    if sport is None:
        raise _not_found("SPORT_NOT_FOUND", "sport_id", league["sport_id"])

    squad_ids = {squad["squad_id"] for squad in squads}
    for player in players:
        if player["squad_id"] is not None and player["squad_id"] not in squad_ids:
            raise _not_found("SQUAD_NOT_FOUND", "squad_id", player["squad_id"])
    for match in matches:
        for key in ("home_squad_id", "away_squad_id"):
            if match[key] not in squad_ids:
                raise _not_found("SQUAD_NOT_FOUND", "squad_id", match[key])

    default_max, default_required = _sport_roster_defaults(sport)
    max_size = league.get("max_squad_size")
    if max_size is None:
        max_size = default_max
    required = league.get("required_positions")
    if required is None:
        required = default_required

    _lock(session)
    clear_league(session, league_id)
    session.add(
        RosterLeague(
            league_id=league_id,
            tenant_id=league["tenant_id"],
            sport_id=league["sport_id"],
            window_open=window_open.isoformat(),
            window_close=window_close.isoformat(),
            max_squad_size=max_size,
            required_positions=dict(required),
        )
    )
    for squad in squads:
        session.add(Squad(league_id=league_id, **squad))
    counts = {squad["squad_id"]: 0 for squad in squads}
    for player in players:
        session.add(
            RosterPlayer(
                league_id=league_id,
                player_id=player["player_id"],
                name=player["name"],
                position=player["position"],
                role=player["role"],
                initial_squad_id=player["squad_id"],
                squad_id=player["squad_id"],
                parent_squad_id=None,
                loan_end_date=None,
                released=False,
            )
        )
        if player["squad_id"] is not None:
            counts[player["squad_id"]] += 1
    for match in matches:
        session.add(
            RosterInMatch(
                league_id=league_id,
                match_id=match["match_id"],
                home_squad_id=match["home_squad_id"],
                away_squad_id=match["away_squad_id"],
            )
        )
    session.flush()
    return {"league_id": league_id, "status": "configured", "squad_counts": counts}


def clear_league(session: Session, league_id: str) -> None:
    for model in (AuditEntry, RosterRequest, RosterInMatch, RosterPlayer, Squad):
        session.execute(delete(model).where(model.league_id == league_id))
    session.execute(delete(RosterLeague).where(RosterLeague.league_id == league_id))
    session.flush()


# ---------------------------------------------------------------- transfer


@dataclass
class TransferRequest:
    request_id: str
    league_id: str
    player_id: str
    type: str
    from_squad_id: str
    to_squad_id: str | None
    effective_date: date
    loan_end_date: date | None
    reason: str | None
    requested_by: str | None
    body_hash: str


@dataclass
class TransferContext:
    league: RosterLeague
    player: RosterPlayer
    from_squad: Squad
    to_squad: Squad | None


def parse_transfer(body: Any) -> TransferRequest:
    """Rule 1: schema, dates, loan_end_date > effective_date, destination present."""
    if not isinstance(body, dict):
        raise _validation(["body"], "Transfer body must be an object")
    fields: set[str] = set()
    for key in ("request_id", "league_id", "player_id", "from_squad_id"):
        if not is_valid_id(body.get(key)):
            fields.add(key)
    move_type = body.get("type")
    if move_type not in MOVE_TYPES:
        fields.add("type")
    to_squad_id = body.get("to_squad_id")
    if move_type == "release":
        to_squad_id = None
    elif not is_valid_id(to_squad_id):
        fields.add("to_squad_id")
    effective = parse_date(body.get("effective_date"))
    if effective is None:
        fields.add("effective_date")
    loan_end = None
    if move_type == "loan":
        loan_end = parse_date(body.get("loan_end_date"))
        if loan_end is None or (effective is not None and loan_end <= effective):
            fields.add("loan_end_date")
    for key in ("reason", "requested_by"):
        value = body.get(key)
        if value is not None and not isinstance(value, str):
            fields.add(key)
    if fields:
        raise _validation(fields, "Transfer request is invalid")
    return TransferRequest(
        request_id=body["request_id"],
        league_id=body["league_id"],
        player_id=body["player_id"],
        type=move_type,
        from_squad_id=body["from_squad_id"],
        to_squad_id=to_squad_id,
        effective_date=effective,  # type: ignore[arg-type]
        loan_end_date=loan_end,
        reason=body.get("reason"),
        requested_by=body.get("requested_by"),
        body_hash=canonical(body),
    )


def find_stored_request(session: Session, req: TransferRequest) -> RosterRequest | None:
    return session.scalars(
        select(RosterRequest).where(
            RosterRequest.league_id == req.league_id,
            RosterRequest.request_id == req.request_id,
        )
    ).first()


def check_replay(session: Session, req: TransferRequest) -> dict[str, Any] | None:
    """Identical replay → stored response; reused id with another body → 400."""
    stored = find_stored_request(session, req)
    if stored is None:
        return None
    if stored.request_hash == req.body_hash:
        return stored.response
    raise ApiError(
        400,
        "VALIDATION_ERROR",
        f"request_id {req.request_id} was already used with a different body.",
        {"fields": ["request_id"]},
    )


def resolve_transfer(session: Session, req: TransferRequest) -> TransferContext:
    """Rule 2: league / player / squads exist."""
    league = session.get(RosterLeague, req.league_id)
    if league is None:
        raise _not_found("LEAGUE_NOT_FOUND", "league_id", req.league_id)
    player = _get_player(session, req.league_id, req.player_id)
    if player is None:
        raise _not_found("PLAYER_NOT_FOUND", "player_id", req.player_id)
    from_squad = _get_squad(session, req.league_id, req.from_squad_id)
    if from_squad is None:
        raise _not_found("SQUAD_NOT_FOUND", "squad_id", req.from_squad_id)
    to_squad = None
    if req.type != "release":
        to_squad = _get_squad(session, req.league_id, req.to_squad_id or "")
        if to_squad is None:
            raise _not_found("SQUAD_NOT_FOUND", "squad_id", req.to_squad_id)
    return TransferContext(league, player, from_squad, to_squad)


def apply_transfer(
    session: Session, req: TransferRequest, ctx: TransferContext
) -> dict[str, Any]:
    """Rules 3-8 in order, then the move, its audit entry and the stored response."""
    league, player, from_squad, to_squad = ctx.league, ctx.player, ctx.from_squad, ctx.to_squad

    # A loan that has ended by the effective date returns first (rolled back on rejection).
    _return_loan_if_expired(session, player, req.effective_date)

    # 3 tenant
    if from_squad.tenant_id != league.tenant_id or (
        to_squad is not None and to_squad.tenant_id != league.tenant_id
    ):
        raise _conflict(
            "CROSS_TENANT_TRANSFER",
            "Squads must belong to the league's tenant.",
            {"tenant_id": league.tenant_id},
        )

    # 4 current squad
    on_loan = player.parent_squad_id is not None
    current = None if player.released else player.squad_id
    if not (
        current == req.from_squad_id
        or (on_loan and player.parent_squad_id == req.from_squad_id)
    ):
        raise _conflict(
            "NOT_IN_SQUAD",
            f"Player {player.player_id} is not registered with squad {req.from_squad_id}.",
            {"player_id": player.player_id, "squad_id": req.from_squad_id},
        )

    # 5 window
    if req.type != "release":
        opens = parse_date(league.window_open)
        closes = parse_date(league.window_close)
        if not (opens <= req.effective_date <= closes):  # type: ignore[operator]
            raise _conflict(
                "TRANSFER_WINDOW_CLOSED",
                "The effective date is outside the transfer window.",
                {
                    "effective_date": req.effective_date.isoformat(),
                    "open": league.window_open,
                    "close": league.window_close,
                },
            )

    # 6 on loan
    if on_loan:
        raise _conflict(
            "PLAYER_ON_LOAN",
            f"Player {player.player_id} is currently on loan.",
            {"player_id": player.player_id, "loan_end_date": player.loan_end_date},
        )

    # 7 destination capacity
    if req.type != "release" and league.max_squad_size is not None and to_squad is not None:
        if _squad_count(session, league.league_id, to_squad.squad_id) + 1 > league.max_squad_size:
            raise _conflict(
                "SQUAD_FULL",
                f"Squad {to_squad.squad_id} is full.",
                {"squad_id": to_squad.squad_id, "max_squad_size": league.max_squad_size},
            )

    # 8 minimum positions left behind
    required = int((league.required_positions or {}).get(player.position, 0) or 0)
    remaining = _position_count(session, league.league_id, from_squad.squad_id, player.position) - 1
    if remaining < required:
        raise _conflict(
            "MIN_POSITION_VIOLATION",
            f"Squad {from_squad.squad_id} would drop below the required {player.position} count.",
            {"squad_id": from_squad.squad_id, "position": player.position, "required": required},
        )

    blocking = session.scalars(
        select(RosterInMatch)
        .where(
            RosterInMatch.league_id == league.league_id,
            (RosterInMatch.home_squad_id == from_squad.squad_id)
            | (RosterInMatch.away_squad_id == from_squad.squad_id),
        )
        .order_by(RosterInMatch.id)
    ).first()
    state = STATE_DEFERRED if blocking is not None else STATE_ACTIVE
    blocking_match_id = blocking.match_id if blocking is not None else None

    entry = _append_audit(
        session,
        league_id=league.league_id,
        player_id=player.player_id,
        action=req.type,
        from_squad_id=req.from_squad_id,
        to_squad_id=req.to_squad_id,
        effective_date=req.effective_date.isoformat(),
        state=state,
        who=req.requested_by,
        why=req.reason,
    )

    registration: dict[str, Any] | None
    if req.type == "release":
        player.squad_id = None
        player.parent_squad_id = None
        player.loan_end_date = None
        player.released = True
        registration = None
    else:
        player.squad_id = req.to_squad_id
        player.role = "substitute"
        player.released = False
        if req.type == "loan":
            player.parent_squad_id = req.from_squad_id
            player.loan_end_date = req.loan_end_date.isoformat()  # type: ignore[union-attr]
        else:
            player.parent_squad_id = None
            player.loan_end_date = None
        registration = {
            "player_id": player.player_id,
            "league_id": league.league_id,
            "squad_id": player.squad_id,
            "parent_squad_id": player.parent_squad_id,
            "registration_type": req.type,
            "start_date": req.effective_date.isoformat(),
            "loan_end_date": player.loan_end_date,
            "role": player.role,
        }

    response = {
        "request_id": req.request_id,
        "status": "accepted",
        "state": state,
        "blocking_match_id": blocking_match_id,
        "registration": registration,
        "audit_entry": _audit_dict(entry),
    }
    session.add(
        RosterRequest(
            league_id=req.league_id,
            request_id=req.request_id,
            request_hash=req.body_hash,
            response=response,
        )
    )
    session.flush()
    return response


def transfer_in_session(session: Session, body: Any) -> tuple[int, dict[str, Any]]:
    req = parse_transfer(body)
    _lock(session)
    stored = check_replay(session, req)
    if stored is not None:
        return 200, stored
    ctx = resolve_transfer(session, req)
    return 201, apply_transfer(session, req, ctx)


def transfer(session: Session | None, body: Any) -> tuple[int, dict[str, Any]]:
    """Public entry point (also for /api/v1). Raises ApiError on rejection."""
    if session is not None:
        return transfer_in_session(session, body)
    with SessionLocal.begin() as own:
        return transfer_in_session(own, body)


# ---------------------------------------------------------------- history


def player_history(session: Session, player_id: str, as_of_raw: str | None) -> dict[str, Any]:
    if as_of_raw is None:
        as_of = today_utc()
    else:
        as_of = parse_date(as_of_raw)
        if as_of is None:
            raise _validation(["as_of"], "as_of must be a YYYY-MM-DD date")
    _lock(session)
    player = _latest_player(session, player_id)
    if player is None:
        raise _not_found("PLAYER_NOT_FOUND", "player_id", player_id)
    _return_loan_if_expired(session, player, as_of)

    entries = list(
        session.scalars(
            select(AuditEntry)
            .where(
                AuditEntry.league_id == player.league_id,
                AuditEntry.player_id == player.player_id,
            )
            .order_by(AuditEntry.seq)
        ).all()
    )
    squad_id = player.initial_squad_id
    parent = None
    as_of_text = as_of.isoformat()
    for entry in entries:
        if entry.effective_date > as_of_text:
            continue
        if entry.action == "release":
            squad_id, parent = None, None
        elif entry.action == "loan":
            squad_id, parent = entry.to_squad_id, entry.from_squad_id
        else:
            squad_id, parent = entry.to_squad_id, None
    return {
        "player_id": player.player_id,
        "as_of": as_of_text,
        "league_id": player.league_id,
        "current_squad_id": squad_id,
        "parent_squad_id": parent,
        "history": [_audit_dict(entry) for entry in entries],
    }


# ---------------------------------------------------------------- app helpers


def _club_squad(session: Session, club_id: str) -> Squad | None:
    return session.scalars(
        select(Squad).where(Squad.club_id == club_id).order_by(Squad.id.desc())
    ).first()


def roster_for_club(
    session: Session, club_id: str
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    squad = _club_squad(session, club_id)
    if squad is None:
        return None, None, []
    players = session.scalars(
        select(RosterPlayer)
        .where(
            RosterPlayer.league_id == squad.league_id,
            RosterPlayer.squad_id == squad.squad_id,
            RosterPlayer.released.is_(False),
        )
        .order_by(RosterPlayer.id)
    ).all()
    rows = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "position": p.position,
            "role": p.role,
            "squad_id": p.squad_id,
            "league_id": p.league_id,
            "audit_count": audit_count(session, p.league_id, p.player_id),
            "on_loan": p.parent_squad_id is not None,
        }
        for p in players
    ]
    return squad.league_id, squad.squad_id, rows


def destination_squads(session: Session, club_id: str) -> list[dict[str, Any]]:
    squad = _club_squad(session, club_id)
    if squad is None:
        return []
    others = session.scalars(
        select(Squad)
        .where(Squad.league_id == squad.league_id, Squad.squad_id != squad.squad_id)
        .order_by(Squad.id)
    ).all()
    return [{"squad_id": s.squad_id, "club_id": s.club_id, "name": s.name} for s in others]
