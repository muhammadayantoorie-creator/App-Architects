"""Tenant reset hook."""

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.tenants.models import Tenant


def seed_tenants(session: Session, _seed: int, _stock: dict) -> None:
    session.add_all(
        [
            Tenant(tenant_id="tenant-alpha", name="Alpha Sports"),
            Tenant(tenant_id="tenant-beta", name="Beta Athletics"),
        ]
    )


register_reset(10, seed_tenants)
