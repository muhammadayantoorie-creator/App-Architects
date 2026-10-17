"""Tenant persistence model."""

from sqlalchemy import String, event, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # White-label branding (colors are "#RRGGBB").
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)


_BRANDING_COLUMNS = (
    ("logo_url", "VARCHAR(512)"),
    ("primary_color", "VARCHAR(7)"),
    ("secondary_color", "VARCHAR(7)"),
)


@event.listens_for(Base.metadata, "after_create")
def _add_missing_branding_columns(_target, connection, **_kw) -> None:
    """create_all() never alters existing tables: upgrade a tenants table from an older volume."""
    try:
        existing = {column["name"] for column in inspect(connection).get_columns("tenants")}
    except Exception:
        return
    for name, ddl in _BRANDING_COLUMNS:
        if name not in existing:
            connection.execute(text(f"ALTER TABLE tenants ADD COLUMN {name} {ddl}"))
