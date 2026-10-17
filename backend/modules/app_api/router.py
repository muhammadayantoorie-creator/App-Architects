"""Production /api/v1 routes used by the mobile app.

Thin wrappers over the same domain services the /audit/v1 grader routes use. Every route
requires a Bearer JWT (backend.core.auth.current_principal) and is rate limited by
backend.core.ratelimit (all /api/v1/* paths).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from backend.core.auth import current_principal, decode_token, principal_from_claims
from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.modules.app_api.models import PinnedProduct
from backend.modules.events.service import append_event, score_match
from backend.modules.leagues.models import League, MatchStream
from backend.modules.sports.models import Sport
from backend.modules.standings.service import get_standings

router = APIRouter(prefix="/api/v1")

ADMIN = "super_admin"
ORGANIZER = "league_organizer"
MANAGER = "club_manager"


# --------------------------------------------------------------------------- helpers


def _uid(p: dict[str, Any]) -> str:
    return str(p.get("user_id") or p.get("sub") or "")


def _forbid(message: str = "Your role cannot perform this action.") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def _live_principal(request: Request) -> dict[str, Any]:
    if request.headers.get("authorization"):
        return current_principal(request)
    token = request.query_params.get("token")
    if not token:
        raise ApiError(401, "UNAUTHENTICATED", "Missing Bearer token")
    return principal_from_claims(decode_token(token))


def _league_visible(p: dict[str, Any], league: League) -> bool:
    return p.get("role") == ADMIN or league.tenant_id in (None, p.get("tenant_id"))


def _require_league(session, p: dict[str, Any], league_id: str) -> League:
    league = session.get(League, league_id)
    if league is None:
        raise ApiError(404, "LEAGUE_NOT_FOUND", f"League {league_id} does not exist.", {"league_id": league_id})
    if not _league_visible(p, league):
        raise _forbid()
    return league


def _team_names(session, team_ids: set[str]) -> dict[str, str]:
    names = {t: t for t in team_ids}
    try:
        from backend.modules.org.models import Club

        for club in session.scalars(select(Club).where(Club.club_id.in_(team_ids))):
            names[club.club_id] = club.name
    except Exception:
        pass
    try:
        from backend.modules.demo.seed import TEAM_NAMES  # type: ignore[attr-defined]

        for team_id, name in TEAM_NAMES.items():
            if team_id in names and names[team_id] == team_id:
                names[team_id] = name
    except Exception:
        pass
    return names


def _fixture_rows(session, league_id: str) -> list[dict[str, Any]]:
    try:
        from backend.modules.demo.service import fixtures_for_league  # type: ignore

        return fixtures_for_league(session, league_id)
    except ImportError:
        pass
    try:
        from backend.modules.demo.seed import fixtures_for_league  # type: ignore

        return fixtures_for_league(session, league_id)
    except ImportError:
        pass
    streams = list(session.scalars(select(MatchStream).where(MatchStream.league_id == league_id)))
    names = _team_names(session, {s.home_team_id for s in streams} | {s.away_team_id for s in streams})
    rows = []
    for s in streams:
        proj = score_match(session, s.match_id)
        rows.append(
            {
                "match_id": s.match_id,
                "home_team_id": s.home_team_id,
                "home_name": names[s.home_team_id],
                "away_team_id": s.away_team_id,
                "away_name": names[s.away_team_id],
                "scheduled_at": None,
                "status": proj["status"],
                "home_score": proj["home"]["score"],
                "away_score": proj["away"]["score"],
                "version": proj["version"],
            }
        )
    return rows


def _scheduled_at(session, match_id: str) -> str | None:
    try:
        from backend.modules.demo.models import DemoSchedule  # type: ignore

        row = session.get(DemoSchedule, match_id)
        return row.scheduled_at if row is not None else None
    except Exception:
        return None


def _pinned(session, match_id: str, tenant_id: str | None) -> dict[str, Any] | None:
    pin = session.get(PinnedProduct, match_id)
    if pin is None:
        return None
    for product in _products(session, tenant_id):
        if product["product_id"] == pin.product_id:
            v = product["variants"][0] if product["variants"] else {}
            return {
                "product_id": product["product_id"],
                "name": product["name"],
                "price_minor": v.get("price_minor"),
                "currency": v.get("currency", "PKR"),
            }
    return None


def _products(session, tenant_id: str | None = None) -> list[dict[str, Any]]:
    from backend.modules.store.service import list_products

    return list_products(session, tenant_id)["items"]


def _match_detail(session, match_id: str) -> dict[str, Any]:
    proj = score_match(session, match_id)
    stream = session.get(MatchStream, match_id)
    names = _team_names(session, {proj["home"]["team_id"], proj["away"]["team_id"]})
    venue = None
    try:
        from backend.modules.org.models import Club

        club = session.get(Club, proj["home"]["team_id"])
        if club is not None:
            venue = {"name": club.home_venue_name}
    except Exception:
        pass
    league = session.get(League, stream.league_id) if stream and stream.league_id else None
    return {
        "match_id": proj["match_id"],
        "league_id": proj.get("league_id"),
        "sport_id": proj["sport_id"],
        "scheduled_at": _scheduled_at(session, match_id),
        "status": proj["status"],
        "outcome": proj["outcome"],
        "version": proj["version"],
        "venue": venue,
        "home": {**proj["home"], "name": names[proj["home"]["team_id"]]},
        "away": {**proj["away"], "name": names[proj["away"]["team_id"]]},
        "events": proj["events"],
        "pinned_product": _pinned(session, match_id, league.tenant_id if league else None),
        "league_visible": stream is not None,
    }


def _can_score(p: dict[str, Any], league_id: str | None) -> bool:
    if p.get("role") == ADMIN:
        return True
    return p.get("role") == ORGANIZER and league_id is not None and league_id in (p.get("league_ids") or [])


# --------------------------------------------------------------------------- reads


@router.get("/leagues")
def leagues(p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        rows = [l for l in session.scalars(select(League)) if _league_visible(p, l)]
    rows.sort(key=lambda l: (l.league_id != "demo-league-ui", l.league_id))
    return {
        "items": [
            {"league_id": l.league_id, "name": l.name or l.league_id, "sport_id": l.sport_id, "tenant_id": l.tenant_id}
            for l in rows
        ]
    }


@router.get("/leagues/{league_id}/fixtures")
def league_fixtures(league_id: str, p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        _require_league(session, p, league_id)
        return {"league_id": league_id, "fixtures": _fixture_rows(session, league_id)}


@router.get("/leagues/{league_id}/standings")
def league_standings(league_id: str, p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        _require_league(session, p, league_id)
        data = get_standings(session, league_id)
        team_ids = {row["team_id"] for row in data.get("table", [])}
        data["team_names"] = _team_names(session, team_ids)
        return data


@router.get("/matches/{match_id}")
def match_detail(match_id: str, p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        stream = session.get(MatchStream, match_id)
        if stream is None:
            raise ApiError(404, "MATCH_NOT_FOUND", f"Match {match_id} does not exist.", {"match_id": match_id})
        if stream.league_id is not None:
            _require_league(session, p, stream.league_id)
        detail = _match_detail(session, match_id)
        detail.pop("league_visible", None)
        return detail


@router.get("/sports/{sport_id}")
def sport(sport_id: str, _p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        row = session.get(Sport, sport_id)
        if row is None:
            raise ApiError(404, "SPORT_NOT_FOUND", f"Sport {sport_id} does not exist.", {"sport_id": sport_id})
        return {"sport_id": row.sport_id, "name": row.name, "scoring_model": row.scoring_model, **row.config}


@router.get("/clubs/{club_id}")
def club(club_id: str, p: dict = Depends(current_principal)) -> dict[str, Any]:
    from backend.modules.org.models import Club

    with SessionLocal() as session:
        row = session.get(Club, club_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", f"Club {club_id} does not exist.", {"club_id": club_id})
        if p.get("role") != ADMIN and row.tenant_id != p.get("tenant_id"):
            raise _forbid()
        roster_league_id, squad_id, roster, destinations = None, None, [], []
        try:
            from backend.modules.roster.service import destination_squads, roster_for_club

            roster_league_id, squad_id, roster = roster_for_club(session, club_id)
            destinations = destination_squads(session, club_id)
        except Exception:
            pass
        from backend.modules.org.models import Player
        from backend.modules.org.router import player_to_dict

        players = session.scalars(
            select(Player).where(Player.club_id == club_id).order_by(Player.player_id)
        ).all()
        return {
            "club_id": row.club_id,
            "tenant_id": row.tenant_id,
            "name": row.name,
            "logo_url": None,
            "home_venue_name": row.home_venue_name,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "players": [player_to_dict(x) for x in players],
            "home_venue": {"name": row.home_venue_name, "latitude": row.latitude, "longitude": row.longitude},
            "social": row.social or {},
            "staff": row.staff or [],
            "roster_league_id": roster_league_id,
            "squad_id": squad_id,
            "roster": roster,
            "destination_squads": destinations,
        }


@router.get("/players/{player_id}/history")
def player_history(player_id: str, p: dict = Depends(current_principal)) -> dict[str, Any]:
    from backend.modules.roster.models import RosterLeague, RosterPlayer
    from backend.modules.roster.service import player_history as history

    with SessionLocal.begin() as session:
        player = session.scalars(
            select(RosterPlayer)
            .where(RosterPlayer.player_id == player_id)
            .order_by(RosterPlayer.id.desc())
        ).first()
        if player is not None and p.get("role") != ADMIN:
            league = session.get(RosterLeague, player.league_id)
            if league is None or league.tenant_id != p.get("tenant_id"):
                raise _forbid()
        return history(session, player_id, None)


@router.get("/store/products")
def products(p: dict = Depends(current_principal)) -> dict[str, Any]:
    with SessionLocal() as session:
        tenant_id = None if p.get("role") == ADMIN else (p.get("tenant_id") or "")
        return {"items": _products(session, tenant_id)}


# --------------------------------------------------------------------------- mutations


@router.post("/checkout")
def checkout(body: Any = Body(...), p: dict = Depends(current_principal)) -> JSONResponse:
    from backend.modules.store.models import Product, Variant
    from backend.modules.store.service import checkout as do_checkout, parse_checkout

    if p.get("role") == "viewer":
        raise _forbid("Viewer accounts cannot buy.")
    request_body = {**body, "customer_id": _uid(p)} if isinstance(body, dict) else body
    parsed = parse_checkout(request_body)
    if p.get("role") != ADMIN:
        with SessionLocal() as session:
            variant_ids = [variant_id for variant_id, _ in parsed.items]
            rows = session.execute(
                select(Variant.variant_id, Product.tenant_id)
                .join(Product, Product.product_id == Variant.product_id)
                .where(Variant.variant_id.in_(variant_ids))
            )
            if any(tenant_id != p.get("tenant_id") for _, tenant_id in rows):
                raise _forbid("Product belongs to another tenant.")
    status, response = do_checkout(request_body)
    return JSONResponse(status_code=status, content=response)


@router.post("/events")
def post_event(body: Any = Body(...), p: dict = Depends(current_principal)) -> JSONResponse:
    match_id = body.get("match_id") if isinstance(body, dict) else None
    with SessionLocal() as session, session.begin():
        stream = session.get(MatchStream, match_id) if isinstance(match_id, str) else None
        if stream is not None and not _can_score(p, stream.league_id):
            raise _forbid()
        if stream is None and p.get("role") not in (ADMIN, ORGANIZER):
            raise _forbid()
        result = append_event(session, body)
    _publish(result.channel)
    return JSONResponse(status_code=result.status_code, content=result.response)


def _club_of_squad(session, league_id: Any, squad_id: Any) -> tuple[str, str] | None:
    from backend.modules.roster.models import Squad

    if not isinstance(league_id, str) or not isinstance(squad_id, str):
        return None
    squad = session.scalars(
        select(Squad).where(Squad.league_id == league_id, Squad.squad_id == squad_id)
    ).first()
    return (squad.club_id, squad.tenant_id) if squad is not None else None


@router.post("/roster/actions")
def roster_action(body: Any = Body(...), p: dict = Depends(current_principal)) -> JSONResponse:
    from backend.modules.roster.service import transfer

    if p.get("role") not in (ADMIN, MANAGER):
        raise _forbid()
    if p.get("role") == MANAGER and isinstance(body, dict):
        with SessionLocal() as session:
            owner = _club_of_squad(session, body.get("league_id"), body.get("from_squad_id"))
            if owner is not None and owner != (p.get("club_id"), p.get("tenant_id")):
                raise _forbid("You can only move players from your own club.")
    status, response = transfer(None, body)
    return JSONResponse(status_code=status, content=response)


ROLES = {"captain", "vice_captain", "starter", "substitute"}


@router.post("/clubs/{club_id}/players")
def add_player(club_id: str, body: Any = Body(...), p: dict = Depends(current_principal)) -> JSONResponse:
    """Register a new player in the club's squad (mobile 'Add player'); audited as action 'add'."""
    from backend.core.ids import is_valid_id
    from backend.modules.roster.models import RosterPlayer
    from backend.modules.roster.service import _append_audit, _club_squad, audit_count, today_utc

    if p.get("role") != ADMIN and not (p.get("role") == MANAGER and p.get("club_id") == club_id):
        raise _forbid()
    if not isinstance(body, dict):
        raise ApiError(400, "VALIDATION_ERROR", "Body must be an object", {"fields": ["body"]})
    name = body.get("name")
    position = body.get("position")
    role = body.get("role") or "substitute"
    fields = set()
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        fields.add("name")
    if not isinstance(position, str) or not position.strip() or len(position) > 64:
        fields.add("position")
    if role not in ROLES:
        fields.add("role")
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "Player details are invalid", {"fields": sorted(fields)})
    with SessionLocal.begin() as session:
        squad = _club_squad(session, club_id)
        if squad is None:
            raise ApiError(404, "SQUAD_NOT_FOUND", f"Club {club_id} has no squad.", {"club_id": club_id})
        request_id = body.get("request_id")
        base = request_id if is_valid_id(request_id) else f"{club_id}-{name.strip()}"
        player_id = "pl-" + "".join(ch for ch in base if ch.isalnum() or ch in "-_.")[:60]
        existing = session.scalars(
            select(RosterPlayer).where(
                RosterPlayer.league_id == squad.league_id, RosterPlayer.player_id == player_id
            )
        ).first()
        if existing is None:
            session.add(
                RosterPlayer(
                    league_id=squad.league_id,
                    player_id=player_id,
                    name=name.strip(),
                    position=position.strip().lower(),
                    role=role,
                    initial_squad_id=squad.squad_id,
                    squad_id=squad.squad_id,
                    parent_squad_id=None,
                    loan_end_date=None,
                    released=False,
                )
            )
            session.flush()
            _append_audit(
                session,
                league_id=squad.league_id,
                player_id=player_id,
                action="add",
                from_squad_id=None,
                to_squad_id=squad.squad_id,
                effective_date=today_utc().isoformat(),
                state="active",
                who=_uid(p),
                why="New registration",
            )
        player = {
            "player_id": player_id,
            "name": name.strip(),
            "position": position.strip().lower(),
            "role": role,
            "squad_id": squad.squad_id,
            "league_id": squad.league_id,
            "audit_count": audit_count(session, squad.league_id, player_id),
            "on_loan": False,
        }
    return JSONResponse(status_code=201 if existing is None else 200, content=player)


@router.post("/offline-sync")
def offline_sync(body: Any = Body(...), p: dict = Depends(current_principal)) -> dict[str, Any]:
    from backend.modules.offline_sync.service import process_offline_sync

    if p.get("role") not in (ADMIN, ORGANIZER, MANAGER):
        raise _forbid()
    if p.get("role") != ADMIN and isinstance(body, dict) and isinstance(body.get("actions"), list):
        with SessionLocal() as session:
            for action in body["actions"]:
                if not isinstance(action, dict):
                    continue
                payload = action.get("payload")
                if not isinstance(payload, dict):
                    continue
                if action.get("type") == "score_event":
                    stream = session.get(MatchStream, payload.get("match_id")) if isinstance(payload.get("match_id"), str) else None
                    if p.get("role") != ORGANIZER or (stream is not None and not _can_score(p, stream.league_id)):
                        raise _forbid()
                elif action.get("type") == "roster_transfer":
                    owner = _club_of_squad(session, payload.get("league_id"), payload.get("from_squad_id"))
                    if p.get("role") != MANAGER or (owner is not None and owner != (p.get("club_id"), p.get("tenant_id"))):
                        raise _forbid()
    return process_offline_sync(body)


@router.post("/matches/{match_id}/pinned-product")
def pin_product(match_id: str, body: Any = Body(...), p: dict = Depends(current_principal)) -> dict[str, Any]:
    from backend.modules.store.models import Product

    product_id = body.get("product_id") if isinstance(body, dict) else None
    if not isinstance(product_id, str):
        raise ApiError(400, "VALIDATION_ERROR", "product_id is required", {"fields": ["product_id"]})
    with SessionLocal.begin() as session:
        stream = session.get(MatchStream, match_id)
        if stream is None:
            raise ApiError(404, "MATCH_NOT_FOUND", f"Match {match_id} does not exist.", {"match_id": match_id})
        if not _can_score(p, stream.league_id):
            raise _forbid()
        league = session.get(League, stream.league_id) if stream.league_id else None
        product = session.get(Product, product_id)
        if product is None:
            raise ApiError(404, "NOT_FOUND", f"Product {product_id} does not exist.", {"product_id": product_id})
        if league is not None and product.tenant_id != league.tenant_id:
            raise _forbid("Product belongs to another tenant.")
        pin = session.get(PinnedProduct, match_id)
        if pin is None:
            session.add(PinnedProduct(match_id=match_id, product_id=product_id))
        else:
            pin.product_id = product_id
        channel = f"live:{stream.league_id or match_id}"
    _publish(channel, {"type": "product_pinned", "match_id": match_id, "product_id": product_id})
    return {"match_id": match_id, "product_id": product_id}


def _publish(channel: str | None, message: dict[str, Any] | None = None) -> None:
    if channel is None:
        return
    try:
        from backend.core.redis_client import get_redis

        get_redis().publish(channel, json.dumps(message) if message else "match_updated")
    except Exception:
        pass


# --------------------------------------------------------------------------- live (SSE)


def _league_snapshot(league_id: str) -> dict[str, dict[str, Any]]:
    with SessionLocal() as session:
        snap: dict[str, dict[str, Any]] = {}
        for stream in session.scalars(select(MatchStream).where(MatchStream.league_id == league_id)):
            proj = score_match(session, stream.match_id)
            pin = session.get(PinnedProduct, stream.match_id)
            snap[stream.match_id] = {
                "match_id": stream.match_id,
                "version": proj["version"],
                "status": proj["status"],
                "home_score": proj["home"]["score"],
                "away_score": proj["away"]["score"],
                "pinned": pin.product_id if pin else None,
            }
        return snap


@router.get("/live")
async def live(request: Request, league_id: str, p: dict = Depends(_live_principal)) -> StreamingResponse:
    with SessionLocal() as session:
        _require_league(session, p, league_id)

    async def stream():
        previous = await asyncio.to_thread(_league_snapshot, league_id)
        yield ": connected\n\n"
        idle = 0
        while not await request.is_disconnected():
            await asyncio.sleep(2)
            idle += 2
            current = await asyncio.to_thread(_league_snapshot, league_id)
            for match_id, row in current.items():
                before = previous.get(match_id)
                if before is None or before["version"] != row["version"]:
                    data = {k: row[k] for k in ("match_id", "version", "status", "home_score", "away_score")}
                    yield f"event: match_updated\ndata: {json.dumps(data)}\n\n"
                    idle = 0
                if before is not None and before["pinned"] != row["pinned"] and row["pinned"]:
                    data = {"match_id": match_id, "product_id": row["pinned"]}
                    yield f"event: product_pinned\ndata: {json.dumps(data)}\n\n"
                    idle = 0
            previous = current
            if idle >= 15:
                idle = 0
                yield ": keep-alive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
