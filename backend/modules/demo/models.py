"""Kick-off times for the demo league fixtures shown in the mobile app."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class DemoSchedule(Base):
    __tablename__ = "demo_schedule"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scheduled_at: Mapped[str] = mapped_column(String(20), nullable=False)
