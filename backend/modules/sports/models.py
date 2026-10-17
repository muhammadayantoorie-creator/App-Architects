"""Persistence model for configurable sport definitions."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class Sport(Base):
    __tablename__ = "sports"

    sport_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    scoring_model: Mapped[str] = mapped_column(String(16), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
