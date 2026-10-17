"""Store service: catalogue listing, inventory, and concurrency-safe checkout.

Checkout pipeline (SPEC 5.12): schema 400 -> idempotency (replay 200 / 409 DUPLICATE_ORDER_ID)
-> variants exist 404 -> discount 400 -> claim order id -> atomic reservation 409 OUT_OF_STOCK
-> mock gateway 402 -> commit sale 201.

Reservation is a conditional UPDATE ... WHERE stock >= q per item inside one transaction, which
is atomic on both PostgreSQL (row locks + re-check) and SQLite (database write lock).
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.db import SessionLocal
from backend.core.errors import ApiError
from backend.core.ids import is_valid_id
from backend.core.redis_client import get_redis
from backend.core.signing import canonical, salt, sign
from backend.core.time import now_iso
from backend.modules.store.models import Discount, Order, Product, Variant
from backend.modules.store.pdf import build_receipt_pdf

CURRENCY = "PKR"
MAX_ITEMS = 10
MAX_QUANTITY = 10
MAX_CUSTOMER_ID = 200
ORDERS_STREAM = "orders.events"

TOKEN_SUCCESS = "tok_success"
TOKEN_CAPTURE_FAIL = "tok_capture_fail"

_variants_table = Variant.__table__

# ---------------------------------------------------------------- mock payment gateway

_counter_lock = threading.Lock()
_counter = itertools.count(1)


def reset_gateway_counter() -> None:
    global _counter
    with _counter_lock:
        _counter = itertools.count(1)


def _next_gateway_number() -> int:
    with _counter_lock:
        return next(_counter)


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    error_code: str | None
    authorization_id: str | None
    capture_id: str | None


def _gateway_charge(token: str) -> GatewayResult:
    """In-process mock gateway: authorize then capture, keyed on the payment token."""
    if token == TOKEN_SUCCESS:
        n = _next_gateway_number()
        return GatewayResult(True, None, f"auth_{n}", f"cap_{n}")
    if token == TOKEN_CAPTURE_FAIL:
        # Authorization succeeds, capture fails; the authorization is voided.
        n = _next_gateway_number()
        return GatewayResult(False, "PAYMENT_CAPTURE_FAILED", f"auth_{n}", None)
    return GatewayResult(False, "PAYMENT_DECLINED", None, None)


# ---------------------------------------------------------------- validation


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class CheckoutRequest:
    order_id: str
    customer_id: str
    items: list[tuple[str, int]]
    discount_code: str | None
    token: str

    def normalized(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "items": [{"variant_id": v, "quantity": q} for v, q in self.items],
            "discount_code": self.discount_code,
            "payment": {"token": self.token},
        }

    def request_hash(self) -> str:
        return hashlib.sha256(canonical(self.normalized()).encode("utf-8")).hexdigest()


def _validation_error(fields: set[str], message: str = "Checkout request is invalid") -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, {"fields": sorted(fields)})


def parse_checkout(body: Any) -> CheckoutRequest:
    if not isinstance(body, dict):
        raise _validation_error({"body"}, "Checkout body must be an object")

    fields: set[str] = set()
    order_id = body.get("order_id")
    if not is_valid_id(order_id):
        fields.add("order_id")

    customer_id = body.get("customer_id")
    if (
        not isinstance(customer_id, str)
        or not (1 <= len(customer_id) <= MAX_CUSTOMER_ID)
        or "\x00" in customer_id  # PostgreSQL text cannot hold NUL; never 5xx
    ):
        fields.add("customer_id")

    items_in = body.get("items")
    items: list[tuple[str, int]] = []
    if not isinstance(items_in, list) or not (1 <= len(items_in) <= MAX_ITEMS):
        fields.add("items")
    else:
        seen: set[str] = set()
        for index, item in enumerate(items_in):
            prefix = f"items.{index}"
            if not isinstance(item, dict):
                fields.add(prefix)
                continue
            variant_id = item.get("variant_id")
            quantity = item.get("quantity")
            ok = True
            if not is_valid_id(variant_id):
                fields.add(f"{prefix}.variant_id")
                ok = False
            elif variant_id in seen:
                fields.add("items")
                fields.add(f"{prefix}.variant_id")
                ok = False
            else:
                seen.add(variant_id)
            if not _is_int(quantity) or not (1 <= quantity <= MAX_QUANTITY):
                fields.add(f"{prefix}.quantity")
                ok = False
            if ok:
                items.append((variant_id, quantity))

    discount_code = body.get("discount_code")
    if discount_code is not None and not isinstance(discount_code, str):
        fields.add("discount_code")

    payment = body.get("payment")
    token = None
    if not isinstance(payment, dict):
        fields.add("payment")
    else:
        token = payment.get("token")
        if not isinstance(token, str):
            fields.add("payment.token")

    if fields:
        raise _validation_error(fields)
    return CheckoutRequest(order_id, customer_id, items, discount_code, token)


# ---------------------------------------------------------------- helpers


def _duplicate(order_id: str) -> ApiError:
    return ApiError(
        409,
        "DUPLICATE_ORDER_ID",
        "order_id was already used with a different request",
        {"order_id": order_id},
    )


def _replay(existing: Order, request_hash: str) -> tuple[int, dict[str, Any]]:
    if existing.request_hash != request_hash:
        raise _duplicate(existing.order_id)
    if existing.status == "paid" and existing.response is not None:
        return 200, existing.response
    # Identical request still in flight: it has not produced a result to replay yet.
    raise ApiError(
        409,
        "DUPLICATE_ORDER_ID",
        "An identical order is still being processed",
        {"order_id": existing.order_id},
    )


def _emit_order_event(order_id: str, status: str, total_minor: int | None) -> None:
    # Best effort: the domain event queue must never fail a committed checkout.
    try:
        get_redis().xadd(
            ORDERS_STREAM,
            {
                "order_id": order_id,
                "status": status,
                "total_minor": str(total_minor if total_minor is not None else 0),
                "at": now_iso(),
            },
        )
    except Exception:
        pass


def _delete_order(order_id: str) -> None:
    try:
        with SessionLocal.begin() as session:
            session.execute(delete(Order).where(Order.order_id == order_id))
    except Exception:
        pass


def _release(items: list[tuple[str, int]], order_id: str) -> None:
    """Return reserved units to available stock and free the order id, atomically."""
    with SessionLocal.begin() as session:
        for variant_id, quantity in sorted(items):
            session.execute(
                update(_variants_table)
                .where(_variants_table.c.variant_id == variant_id)
                .values(
                    stock=_variants_table.c.stock + quantity,
                    reserved=_variants_table.c.reserved - quantity,
                )
            )
        session.execute(delete(Order).where(Order.order_id == order_id))


class _OutOfStock(Exception):
    def __init__(self, variant_id: str) -> None:
        super().__init__(variant_id)
        self.variant_id = variant_id


def _reserve(items: list[tuple[str, int]]) -> None:
    """All-or-nothing reservation. Sorted ids give a stable lock order (no PG deadlocks)."""
    with SessionLocal.begin() as session:
        for variant_id, quantity in sorted(items):
            result = session.execute(
                update(_variants_table)
                .where(
                    _variants_table.c.variant_id == variant_id,
                    _variants_table.c.stock >= quantity,
                )
                .values(
                    stock=_variants_table.c.stock - quantity,
                    reserved=_variants_table.c.reserved + quantity,
                )
            )
            if result.rowcount != 1:
                raise _OutOfStock(variant_id)  # rolls back the whole transaction


# ---------------------------------------------------------------- checkout


def checkout(body: Any) -> tuple[int, dict[str, Any]]:
    """Run one checkout. Returns (status_code, response) or raises ApiError."""
    req = parse_checkout(body)
    request_hash = req.request_hash()

    # 1) idempotency, 2) variants exist (404), 3) discount (400) -- read-only.
    with SessionLocal() as session:
        existing = session.get(Order, req.order_id)
        if existing is not None:
            return _replay(existing, request_hash)

        ids = [variant_id for variant_id, _ in req.items]
        found = {
            v.variant_id: v
            for v in session.scalars(select(Variant).where(Variant.variant_id.in_(ids)))
        }
        for variant_id in ids:
            if variant_id not in found:
                raise ApiError(
                    404,
                    "VARIANT_NOT_FOUND",
                    "Variant does not exist",
                    {"variant_id": variant_id},
                )
        prices = {v.variant_id: v.price_minor for v in found.values()}

        percent = 0
        if req.discount_code is not None:
            code = req.discount_code
            discount = (
                session.get(Discount, code)
                if 0 < len(code) <= 64 and "\x00" not in code
                else None
            )
            if discount is None:
                raise ApiError(
                    400,
                    "INVALID_DISCOUNT_CODE",
                    "Discount code is not valid",
                    {"discount_code": req.discount_code},
                )
            percent = discount.percent

    # Claim the order id first (unique primary key) so a concurrent replay cannot double-sell.
    try:
        with SessionLocal.begin() as session:
            session.add(
                Order(
                    order_id=req.order_id,
                    request_hash=request_hash,
                    status="pending",
                    customer_id=req.customer_id,
                    total_minor=None,
                    response=None,
                    created_at=now_iso(),
                )
            )
    except IntegrityError:
        with SessionLocal() as session:
            existing = session.get(Order, req.order_id)
            if existing is None:
                raise _duplicate(req.order_id)
            return _replay(existing, request_hash)

    # Atomic all-or-nothing reservation, committed before talking to the gateway.
    try:
        _reserve(req.items)
    except _OutOfStock as exc:
        _delete_order(req.order_id)
        raise ApiError(
            409,
            "OUT_OF_STOCK",
            "Insufficient stock for variant",
            {"variant_id": exc.variant_id},
        ) from None
    except Exception:
        _delete_order(req.order_id)
        raise

    gateway = _gateway_charge(req.token)
    if not gateway.ok:
        _release(req.items, req.order_id)
        _emit_order_event(req.order_id, "payment_failed", None)
        if gateway.error_code == "PAYMENT_CAPTURE_FAILED":
            raise ApiError(
                402,
                "PAYMENT_CAPTURE_FAILED",
                "Payment capture failed; authorization voided",
                {"order_id": req.order_id},
            )
        raise ApiError(
            402,
            "PAYMENT_DECLINED",
            "Payment authorization was declined",
            {"order_id": req.order_id},
        )

    try:
        response = _build_response(req, prices, percent, gateway)
        with SessionLocal.begin() as session:
            for variant_id, quantity in sorted(req.items):
                session.execute(
                    update(_variants_table)
                    .where(_variants_table.c.variant_id == variant_id)
                    .values(reserved=_variants_table.c.reserved - quantity)
                )
            session.execute(
                update(Order)
                .where(Order.order_id == req.order_id)
                .values(
                    status="paid",
                    total_minor=response["total_minor"],
                    response=response,
                )
                .execution_options(synchronize_session=False)
            )
    except Exception:
        try:
            _release(req.items, req.order_id)
        except Exception:
            pass
        raise

    _emit_order_event(req.order_id, "paid", response["total_minor"])
    return 201, response


def _build_response(
    req: CheckoutRequest,
    prices: dict[str, int],
    percent: int,
    gateway: GatewayResult,
) -> dict[str, Any]:
    items = [
        {"variant_id": variant_id, "quantity": quantity, "unit_price_minor": prices[variant_id]}
        for variant_id, quantity in req.items
    ]
    subtotal = sum(item["quantity"] * item["unit_price_minor"] for item in items)
    discount_minor = subtotal * percent // 100
    total = subtotal - discount_minor

    payload = {
        "order_id": req.order_id,
        "customer_id": req.customer_id,
        "items": [dict(item) for item in items],
        "subtotal_minor": subtotal,
        "discount_minor": discount_minor,
        "total_minor": total,
        "currency": CURRENCY,
        "paid_at": now_iso(),
    }
    signature = sign(salt(), req.order_id, payload)
    pdf_base64 = base64.b64encode(build_receipt_pdf(payload)).decode("ascii")

    return {
        "order_id": req.order_id,
        "status": "paid",
        "currency": CURRENCY,
        "items": items,
        "subtotal_minor": subtotal,
        "discount_minor": discount_minor,
        "total_minor": total,
        "payment": {
            "authorization_id": gateway.authorization_id,
            "capture_id": gateway.capture_id,
            "state": "captured",
        },
        "receipt": {
            "payload": payload,
            "signature": signature,
            "pdf_base64": pdf_base64,
        },
    }


# ---------------------------------------------------------------- reads


def get_inventory(session: Session, variant_id: str) -> dict[str, Any]:
    variant = session.get(Variant, variant_id) if is_valid_id(variant_id) else None
    if variant is None:
        raise ApiError(
            404, "VARIANT_NOT_FOUND", "Variant does not exist", {"variant_id": variant_id}
        )
    return {"variant_id": variant.variant_id, "stock": variant.stock, "reserved": variant.reserved}


def list_products(session: Session, tenant_id: str | None = None) -> dict[str, Any]:
    products_query = select(Product)
    if tenant_id is not None:
        products_query = products_query.where(Product.tenant_id == tenant_id)
    products = session.scalars(
        products_query.order_by(Product.position, Product.product_id)
    ).all()
    product_ids = [product.product_id for product in products]
    variants = session.scalars(
        select(Variant)
        .where(Variant.product_id.in_(product_ids))
        .order_by(Variant.product_id, Variant.position, Variant.variant_id)
    ).all() if product_ids else []
    by_product: dict[str, list[dict[str, Any]]] = {}
    for v in variants:
        by_product.setdefault(v.product_id, []).append(
            {
                "variant_id": v.variant_id,
                "label": v.label,
                "price_minor": v.price_minor,
                "currency": v.currency,
                "stock": v.stock,
            }
        )
    return {
        "items": [
            {
                "product_id": p.product_id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "variants": by_product.get(p.product_id, []),
            }
            for p in products
        ]
    }
