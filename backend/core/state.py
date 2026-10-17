"""Small persistent application state values, such as the last reset seed."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class CoreState(Base):
    __tablename__ = "core_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


def set_value(session, key: str, value: str) -> None:
    row = session.get(CoreState, key)
    if row is None:
        session.add(CoreState(key=key, value=value))
    else:
        row.value = value


def get_value(session, key: str, default: str | None = None) -> str | None:
    row = session.get(CoreState, key)
    return row.value if row is not None else default


def baseline_is_seeded(session) -> bool:
    """Only the final ordered seed hook may publish this readiness marker."""
    return get_value(session, "baseline_complete") == "1"
