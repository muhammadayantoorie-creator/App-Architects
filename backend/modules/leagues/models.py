"""Relational league, team membership, and fixture stream models."""

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class League(Base):
    __tablename__ = "leagues"

    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sport_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("sports.sport_id"), nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    points: Mapped[dict] = mapped_column(JSON, nullable=False)
    tie_break_order: Mapped[list] = mapped_column(JSON, nullable=False)
    qualification_spots: Mapped[int] = mapped_column(Integer, nullable=False)
    lots_seed: Mapped[int] = mapped_column(Integer, nullable=False)


class LeagueTeam(Base):
    __tablename__ = "league_teams"

    league_id: Mapped[str] = mapped_column(
        ForeignKey("leagues.league_id", ondelete="CASCADE"), primary_key=True
    )
    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class MatchStream(Base):
    __tablename__ = "match_streams"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sport_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("sports.sport_id"), nullable=False
    )
    league_id: Mapped[str | None] = mapped_column(
        ForeignKey("leagues.league_id", ondelete="CASCADE"), nullable=True
    )
    home_team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    away_team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="upcoming")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draw_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
