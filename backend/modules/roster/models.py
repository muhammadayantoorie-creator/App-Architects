"""Roster registration state, kept separate from the org/club module tables.

Squads and players are scoped to a roster league (surrogate primary keys plus a
unique (league_id, id) pair) so independent setup scenarios may reuse ids.
"""

from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class RosterLeague(Base):
    __tablename__ = "roster_leagues"

    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sport_id: Mapped[str] = mapped_column(String(64), nullable=False)
    window_open: Mapped[str] = mapped_column(String(10), nullable=False)
    window_close: Mapped[str] = mapped_column(String(10), nullable=False)
    max_squad_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_positions: Mapped[dict] = mapped_column(JSON, nullable=False)


class Squad(Base):
    __tablename__ = "roster_squads"
    __table_args__ = (UniqueConstraint("league_id", "squad_id", name="uq_roster_squad"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    squad_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    club_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class RosterPlayer(Base):
    __tablename__ = "roster_players"
    __table_args__ = (UniqueConstraint("league_id", "player_id", name="uq_roster_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    loan_end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    released: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RosterInMatch(Base):
    __tablename__ = "roster_in_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    match_id: Mapped[str] = mapped_column(String(64), nullable=False)
    home_squad_id: Mapped[str] = mapped_column(String(64), nullable=False)
    away_squad_id: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEntry(Base):
    __tablename__ = "roster_audit_entries"

    audit_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    league_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    who: Mapped[str | None] = mapped_column(Text, nullable=True)
    when_at: Mapped[str] = mapped_column("occurred_at", String(20), nullable=False)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)


class RosterRequest(Base):
    __tablename__ = "roster_requests"
    __table_args__ = (
        UniqueConstraint("league_id", "request_id", name="uq_roster_request"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
