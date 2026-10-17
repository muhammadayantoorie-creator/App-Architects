"""State owned by the mobile-app API (pinned product showcase per match)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


class PinnedProduct(Base):
    __tablename__ = "app_pinned_products"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
