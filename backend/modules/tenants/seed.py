"""Tenant reset hook."""

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.tenants.models import Tenant

BASELINE_TENANTS = [
    {
        "tenant_id": "tenant-alpha",
        "name": "Alpha Sports",
        "logo_url": "https://placehold.co/256x256/1565C0/FFB300.png?text=Alpha",
        "primary_color": "#1565C0",
        "secondary_color": "#FFB300",
    },
    {
        "tenant_id": "tenant-beta",
        "name": "Beta Athletics",
        "logo_url": "https://placehold.co/256x256/2E7D32/FFFFFF.png?text=Beta",
        "primary_color": "#2E7D32",
        "secondary_color": "#FFFFFF",
    },
]


def seed_tenants(session: Session, _seed: int, _stock: dict) -> None:
    session.add_all([Tenant(**tenant) for tenant in BASELINE_TENANTS])


register_reset(10, seed_tenants)
