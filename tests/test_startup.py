from tests.conftest import assert_error


def test_health_ok_after_startup(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_reset_response_and_repeatable(client):
    expected = {
        "status": "reset_complete",
        "seed": 42,
        "sports": ["football", "basketball", "cricket", "esports"],
        "tenants": ["tenant-alpha", "tenant-beta"],
        "stock": {"var-jersey-001-M": 1, "var-jersey-001-L": 5},
    }
    for _ in range(2):
        r = client.post("/audit/v1/reset")
        assert r.status_code == 200
        assert r.json() == expected
        assert client.get("/health").status_code == 200


def test_reset_custom_seed_and_stock(client):
    r = client.post("/audit/v1/reset", json={"seed": 7, "stock": {"var-jersey-001-M": 3}})
    assert r.status_code == 200
    assert r.json()["seed"] == 7
    assert r.json()["stock"] == {"var-jersey-001-M": 3, "var-jersey-001-L": 5}


def test_reset_validation_error(client):
    assert_error(client.post("/audit/v1/reset", json={"seed": "x"}), 400, "VALIDATION_ERROR")


def test_unknown_route_uses_error_envelope(client):
    assert_error(client.get("/audit/v1/nope"), 404, "NOT_FOUND")


def test_body_over_1mb_is_413(client):
    big = "x" * (1_048_576 + 10)
    r = client.post("/audit/v1/sports", content=big, headers={"Content-Type": "application/json"})
    assert_error(r, 413, "PAYLOAD_TOO_LARGE")
