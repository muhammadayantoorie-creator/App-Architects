"""Store baseline: the graded jersey product plus mobile demo catalogue."""

from typing import Any

from sqlalchemy.orm import Session

from backend.core.registry import register_reset
from backend.modules.store.models import Discount, Product, Variant

# (product_id, tenant_id, name, category, description, variants)
# variant = (variant_id, label, price_minor, default_stock)
BASELINE_PRODUCTS: list[tuple[str, str, str, str, str, list[tuple[str, str, int, int]]]] = [
    (
        "demo-prod-scarf",
        "tenant-alpha",
        "Alpha Scarf",
        "accessories",
        "Knitted supporters scarf in club colours.",
        [("demo-var-scarf-std", "Standard", 150000, 100)],
    ),
    (
        "prod-jersey-001",
        "tenant-alpha",
        "Alpha Home Jersey",
        "apparel",
        "Official Alpha Sports home jersey.",
        [
            ("var-jersey-001-M", "M", 450000, 1),
            ("var-jersey-001-L", "L", 450000, 5),
        ],
    ),
    (
        "demo-prod-cap",
        "tenant-alpha",
        "Alpha Cap",
        "accessories",
        "Embroidered club cap.",
        [("demo-var-cap", "One size", 120000, 0)],
    ),
]

BASELINE_DISCOUNTS = [("WELCOME10", 10)]


def _stock_for(stock: dict[str, Any], variant_id: str, default: int) -> int:
    value = stock.get(variant_id, default) if isinstance(stock, dict) else default
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return default


def seed_store(session: Session, _seed: int, stock: dict[str, Any]) -> None:
    from backend.modules.store.service import reset_gateway_counter

    for position, (product_id, tenant_id, name, category, description, variants) in enumerate(
        BASELINE_PRODUCTS
    ):
        session.add(
            Product(
                product_id=product_id,
                tenant_id=tenant_id,
                name=name,
                category=category,
                description=description,
                position=position,
            )
        )
        session.flush()
        for v_position, (variant_id, label, price_minor, default_stock) in enumerate(variants):
            session.add(
                Variant(
                    variant_id=variant_id,
                    product_id=product_id,
                    label=label,
                    price_minor=price_minor,
                    currency="PKR",
                    stock=_stock_for(stock or {}, variant_id, default_stock),
                    reserved=0,
                    position=v_position,
                )
            )
    for code, percent in BASELINE_DISCOUNTS:
        session.add(Discount(code=code, percent=percent))
    session.flush()
    reset_gateway_counter()


register_reset(40, seed_store)
