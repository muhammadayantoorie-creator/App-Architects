"""Organisation models: clubs, players and platform users (RBAC scenario).

Table names carry an ``org_`` prefix so they never collide with tables other
modules (e.g. roster squads/players) may define.
"""

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class Club(Base):
    __tablename__ = "org_clubs"

    club_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    home_venue_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    social: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    staff: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class Player(Base):
    __tablename__ = "org_players"

    player_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id"), nullable=False
    )
    club_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("org_clubs.club_id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)


class User(Base):
    __tablename__ = "org_users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id"), nullable=True
    )
    club_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    player_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    league_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
