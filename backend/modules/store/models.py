"""Store persistence: products, variants with stock counters, discounts, orders."""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class Product(Base):
    __tablename__ = "store_products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Variant(Base):
    __tablename__ = "store_variants"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_store_variants_stock_nonneg"),
        CheckConstraint("reserved >= 0", name="ck_store_variants_reserved_nonneg"),
    )

    variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("store_products.product_id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Discount(Base):
    __tablename__ = "store_discounts"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)


class Order(Base):
    __tablename__ = "store_orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(200), nullable=False)
    total_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(20), nullable=False)
