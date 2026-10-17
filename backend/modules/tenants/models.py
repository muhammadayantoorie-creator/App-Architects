"""Tenant persistence model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
