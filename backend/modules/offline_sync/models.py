"""Processed offline actions, keyed by (device_id, action_id)."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class OfflineSyncAction(Base):
    __tablename__ = "offline_sync_actions"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[str] = mapped_column(String(20), nullable=False)
