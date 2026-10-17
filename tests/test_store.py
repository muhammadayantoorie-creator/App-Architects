import base64
import threading

from backend.core.signing import salt, sign
from tests.conftest import assert_error

M = "var-jersey-001-M"
L = "var-jersey-001-L"


def _body(order_id="ord-001", items=None, discount_code=None, token="tok_success", customer_id="cust-001"):
    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "items": items if items is not None else [{"variant_id": M, "quantity": 1}],
        "discount_code": discount_code,
        "payment": {"token": token},
    }


def _inv(client, variant_id):
    r = client.get(f"/audit/v1/inventory/{variant_id}")
    assert r.status_code == 200, r.text
    return r.json()


def test_happy_path_exact_shape(client, reset):
    r = client.post("/audit/v1/checkout", json=_body())
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {
        "order_id", "status", "currency", "items", "subtotal_minor",
        "discount_minor", "total_minor", "payment", "receipt",
    }
    assert body["order_id"] == "ord-001"
    assert body["status"] == "paid"
    assert body["currency"] == "PKR"
    item = {"variant_id": M, "quantity": 1, "unit_price_minor": 450000}
    assert body["items"] == [item]
    assert (body["subtotal_minor"], body["discount_minor"], body["total_minor"]) == (450000, 0, 450000)
    assert body["payment"]["state"] == "captured"
    assert body["payment"]["authorization_id"].startswith("auth_")
    assert body["payment"]["capture_id"].startswith("cap_")
    assert set(body["receipt"]) == {"payload", "signature", "pdf_base64"}
    payload = body["receipt"]["payload"]
    assert set(payload) == {
        "order_id", "customer_id", "items", "subtotal_minor", "discount_minor",
        "total_minor", "currency", "paid_at",
    }
    assert payload["order_id"] == "ord-001"
    assert payload["customer_id"] == "cust-001"
    assert payload["items"] == [item]
    assert payload["currency"] == "PKR"
    assert payload["total_minor"] == 450000
    assert len(payload["paid_at"]) == 20 and payload["paid_at"].endswith("Z")
    assert body["receipt"]["signature"] == sign(salt(), "ord-001", payload)
    pdf = base64.b64decode(body["receipt"]["pdf_base64"])
    assert pdf.startswith(b"%PDF")
    assert b"ord-001" in pdf
    assert b"PKR 4500.00" in pdf
    assert _inv(client, M) == {"variant_id": M, "stock": 0, "reserved": 0}


def test_replay_identical_returns_200_same_body(client, reset):
    first = client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": L, "quantity": 2}]))
    assert first.status_code == 201
    again = client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": L, "quantity": 2}]))
    assert again.status_code == 200
    assert again.json() == first.json()
    assert _inv(client, L) == {"variant_id": L, "stock": 3, "reserved": 0}


def test_same_order_id_different_body_409(client, reset):
    assert client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": L, "quantity": 1}])).status_code == 201
    r = client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": L, "quantity": 2}]))
    assert_error(r, 409, "DUPLICATE_ORDER_ID")
    assert _inv(client, L)["stock"] == 4


def test_unknown_variant_404(client, reset):
    r = client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": "var-nope", "quantity": 1}]))
    err = assert_error(r, 404, "VARIANT_NOT_FOUND")
    assert err["details"]["variant_id"] == "var-nope"
    assert_error(client.get("/audit/v1/inventory/var-nope"), 404, "VARIANT_NOT_FOUND")


def test_bad_discount_400(client, reset):
    r = client.post("/audit/v1/checkout", json=_body(discount_code="FREE100"))
    assert_error(r, 400, "INVALID_DISCOUNT_CODE")
    assert _inv(client, M)["stock"] == 1


def test_unknown_variant_wins_over_bad_discount(client, reset):
    r = client.post("/audit/v1/checkout", json=_body(items=[{"variant_id": "var-x", "quantity": 1}], discount_code="NOPE"))
    assert_error(r, 404, "VARIANT_NOT_FOUND")


def test_welcome10_discount_math(client, reset):
    r = client.post(
        "/audit/v1/checkout",
        json=_body(items=[{"variant_id": L, "quantity": 3}, {"variant_id": M, "quantity": 1}], discount_code="WELCOME10"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subtotal_minor"] == 1800000
    assert body["discount_minor"] == 180000
    assert body["total_minor"] == 1620000
    assert body["receipt"]["payload"]["discount_minor"] == 180000
    pdf = base64.b64decode(body["receipt"]["pdf_base64"])
    assert b"PKR 16200.00" in pdf
    assert body["items"][0]["variant_id"] == L


def test_declined_402_and_stock_restored(client, reset):
    r = client.post("/audit/v1/checkout", json=_body(token="tok_declined"))
    assert_error(r, 402, "PAYMENT_DECLINED")
    assert _inv(client, M) == {"variant_id": M, "stock": 1, "reserved": 0}
    # released stock is purchasable again, and the failed order id can be retried
    assert client.post("/audit/v1/checkout", json=_body(order_id="ord-002")).status_code == 201


def test_capture_fail_402_and_stock_restored(client, reset):
    r = client.post("/audit/v1/checkout", json=_body(token="tok_capture_fail"))
    assert_error(r, 402, "PAYMENT_CAPTURE_FAILED")
    assert _inv(client, M) == {"variant_id": M, "stock": 1, "reserved": 0}
    r = client.post("/audit/v1/checkout", json=_body(token="tok_success"))
    assert r.status_code == 201


def test_out_of_stock_409_reserves_nothing(client, reset):
    r = client.post(
        "/audit/v1/checkout",
        json=_body(items=[{"variant_id": L, "quantity": 2}, {"variant_id": M, "quantity": 2}]),
    )
    err = assert_error(r, 409, "OUT_OF_STOCK")
    assert err["details"]["variant_id"] == M
    assert _inv(client, L) == {"variant_id": L, "stock": 5, "reserved": 0}
    assert _inv(client, M) == {"variant_id": M, "stock": 1, "reserved": 0}


def test_validation_errors(client, reset):
    cases = [
        _body(items=[{"variant_id": M, "quantity": 0}]),
        _body(items=[{"variant_id": M, "quantity": 11}]),
        _body(items=[{"variant_id": M, "quantity": True}]),
        _body(items=[{"variant_id": M, "quantity": "1"}]),
        _body(items=[{"variant_id": f"v{i}", "quantity": 1} for i in range(11)]),
        _body(items=[]),
        _body(items=[{"variant_id": M, "quantity": 1}, {"variant_id": M, "quantity": 1}]),
        _body(order_id="bad|id"),
        _body(customer_id=""),
        _body(customer_id="x" * 201),
        {**_body(), "payment": {}},
        {**_body(), "payment": None},
        {**_body(), "discount_code": 5},
        [],
    ]
    for case in cases:
        r = client.post("/audit/v1/checkout", json=case)
        err = assert_error(r, 400, "VALIDATION_ERROR")
        assert isinstance(err["details"]["fields"], list) and err["details"]["fields"], case
    r = client.post("/audit/v1/checkout", content=b"{bad", headers={"Content-Type": "application/json"})
    assert_error(r, 400, "VALIDATION_ERROR")
    assert _inv(client, M)["stock"] == 1


def test_customer_id_stored_verbatim(client, reset):
    nasty = "cust \"quoted\" <script>alert(1)</script> x'; DROP TABLE store_orders;--"
    r = client.post("/audit/v1/checkout", json=_body(customer_id=nasty))
    assert r.status_code == 201, r.text
    assert r.json()["receipt"]["payload"]["customer_id"] == nasty
    assert client.post("/audit/v1/checkout", json=_body(customer_id=nasty)).status_code == 200


def test_list_products_and_seed_stock_map(client):
    r = client.post("/audit/v1/reset", json={"stock": {M: 4, "demo-var-scarf-std": 7}})
    assert r.status_code == 200
    from backend.core.db import SessionLocal
    from backend.modules.store.service import list_products

    with SessionLocal() as session:
        data = list_products(session)
    ids = [p["product_id"] for p in data["items"]]
    assert ids[0] == "demo-prod-scarf"
    assert "prod-jersey-001" in ids and "demo-prod-cap" in ids
    jersey = next(p for p in data["items"] if p["product_id"] == "prod-jersey-001")
    stocks = {v["variant_id"]: v["stock"] for v in jersey["variants"]}
    assert stocks == {M: 4, L: 5}
    assert data["items"][0]["variants"][0]["stock"] == 7
    assert _inv(client, M)["stock"] == 4


def test_concurrent_last_unit_exactly_one_sale(client):
    assert client.post("/audit/v1/reset", json={"stock": {M: 1}}).status_code == 200
    n = 20
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        barrier.wait()
        r = client.post("/audit/v1/checkout", json=_body(order_id=f"burst-{i:02d}", customer_id=f"c{i}"))
        results[i] = (r.status_code, r.json())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    codes = sorted(code for code, _ in results)
    assert codes.count(201) == 1, results
    assert codes.count(409) == n - 1, results
    for code, body in results:
        if code == 409:
            assert body["error"]["code"] == "OUT_OF_STOCK"
            assert body["error"]["details"] == {"variant_id": M}
    assert _inv(client, M) == {"variant_id": M, "stock": 0, "reserved": 0}
