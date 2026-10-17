import time

import pytest

from backend.core import ratelimit
from backend.core.redis_client import get_redis
from tests.conftest import assert_error

DEMO = [
    ("admin@nascon.test", "super_admin", "user-admin", None),
    ("organizer@nascon.test", "league_organizer", "user-organizer", "tenant-alpha"),
    ("manager@nascon.test", "club_manager", "user-manager", "tenant-alpha"),
    ("player@nascon.test", "player", "user-player", "tenant-alpha"),
    ("viewer@nascon.test", "viewer", "user-viewer", "tenant-alpha"),
]


def _cleanup_ip(ip: str) -> None:
    try:
        get_redis().delete(ratelimit.KEY_PREFIX + ip)
    except Exception:
        pass
    ratelimit.reset_local_state()


@pytest.fixture
def ip(request):
    value = f"10.99.{abs(hash(request.node.name)) % 250}.{int(time.time() * 1000) % 250}"
    _cleanup_ip(value)
    yield value
    _cleanup_ip(value)


def _login(client, email, password, ip):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


@pytest.mark.parametrize("email,role,user_id,tenant_id", DEMO)
def test_login_demo_users(client, reset, ip, email, role, user_id, tenant_id):
    r = _login(client, email, "Nascon@26", ip)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert isinstance(body["access_token"], str) and body["access_token"].count(".") == 2
    assert body["user"]["user_id"] == user_id
    assert body["user"]["email"] == email
    assert body["user"]["role"] == role
    assert body["user"]["tenant_id"] == tenant_id
    assert set(body["user"]) == {"user_id", "email", "role", "tenant_id", "club_id", "player_id", "league_ids"}


def test_login_user_bindings(client, reset, ip):
    users = {email: _login(client, email, "Nascon@26", ip).json()["user"] for email, *_ in DEMO}
    assert users["organizer@nascon.test"]["league_ids"] == ["league-alpha-1", "demo-league-ui"]
    assert users["manager@nascon.test"]["club_id"] == "club-alpha-1"
    assert users["player@nascon.test"]["player_id"] == "player-alpha-1"
    assert users["player@nascon.test"]["club_id"] == "club-alpha-1"


def test_login_email_case_insensitive(client, reset, ip):
    assert _login(client, "  Admin@NASCON.test ", "Nascon@26", ip).status_code == 200


def test_login_wrong_password_401(client, reset, ip):
    assert_error(_login(client, "admin@nascon.test", "wrong", ip), 401, "UNAUTHENTICATED")
    assert_error(_login(client, "nobody@nascon.test", "Nascon@26", ip), 401, "UNAUTHENTICATED")


def test_login_validation_400(client, reset, ip):
    headers = {"X-Forwarded-For": ip}
    err = assert_error(client.post("/api/v1/auth/login", json={"email": "a@b.c"}, headers=headers), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["password"]
    err = assert_error(client.post("/api/v1/auth/login", json={"email": 5, "password": 7}, headers=headers), 400, "VALIDATION_ERROR")
    assert err["details"]["fields"] == ["email", "password"]
    assert_error(client.post("/api/v1/auth/login", json=[1, 2], headers=headers), 400, "VALIDATION_ERROR")
    assert_error(client.post("/api/v1/auth/login", headers=headers), 400, "VALIDATION_ERROR")
    r = client.post("/api/v1/auth/login", content=b"{bad", headers={**headers, "Content-Type": "application/json"})
    assert_error(r, 400, "VALIDATION_ERROR")


def test_me(client, reset, ip):
    token = _login(client, "manager@nascon.test", "Nascon@26", ip).json()["access_token"]
    r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": ip})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "user_id": "user-manager",
        "email": "manager@nascon.test",
        "role": "club_manager",
        "tenant": {
            "tenant_id": "tenant-alpha",
            "name": "Alpha Sports",
            "logo_url": r.json()["tenant"]["logo_url"],
            "primary_color": "#1565C0",
            "secondary_color": "#FFB300",
        },
        "club_id": "club-alpha-1",
        "player_id": None,
        "league_ids": [],
    }


def test_me_super_admin_has_null_tenant(client, reset, ip):
    token = _login(client, "admin@nascon.test", "Nascon@26", ip).json()["access_token"]
    r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": ip})
    assert r.status_code == 200
    assert r.json()["tenant"] is None


def test_me_requires_token(client, reset, ip):
    assert_error(client.get("/api/v1/me", headers={"X-Forwarded-For": ip}), 401, "UNAUTHENTICATED")


def test_clubs_tenant_scoped(client, reset, ip):
    token = _login(client, "viewer@nascon.test", "Nascon@26", ip).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": ip}
    r = client.get("/api/v1/clubs", headers=headers)
    assert r.status_code == 200
    assert [c["club_id"] for c in r.json()["clubs"]] == ["club-alpha-1", "club-alpha-2"]
    r = client.get("/api/v1/clubs/club-alpha-1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Alpha FC"
    assert body["social"] == {"x": "@alphafc", "instagram": "alphafc"}
    assert [p["player_id"] for p in body["players"]] == ["player-alpha-1"]
    assert_error(client.get("/api/v1/clubs/club-beta-1", headers=headers), 403, "FORBIDDEN")


def test_ping(client, ip):
    r = client.get("/api/v1/ping", headers={"X-Forwarded-For": ip})
    assert r.status_code == 200
    assert r.json() == {"pong": True}


def test_rate_limit_burst(client, ip):
    headers = {"X-Forwarded-For": ip}
    codes = []
    limited = []
    for _ in range(150):
        r = client.get("/api/v1/ping", headers=headers)
        codes.append(r.status_code)
        if r.status_code == 429:
            limited.append(r)
    assert codes[0] == 200
    assert codes[:100] == [200] * 100
    assert len(limited) >= 40
    for r in limited[:3]:
        assert_error(r, 429, "RATE_LIMITED")
        assert int(r.headers["Retry-After"]) >= 1
    # Exempt paths are never limited, even from the throttled client.
    assert client.post("/audit/v1/reset", json={}, headers=headers).status_code == 200
    for _ in range(5):
        assert client.get("/health", headers=headers).status_code == 200
    # Other clients are unaffected.
    assert client.get("/api/v1/ping", headers={"X-Forwarded-For": ip + "9"}).status_code == 200
    _cleanup_ip(ip + "9")


def test_rate_limit_window_slides():
    ip = "10.250.250.250"
    _cleanup_ip(ip)
    try:
        start = 1_000_000.0
        for i in range(100):
            assert ratelimit.check_rate_limit(ip, start + i * 0.01)[0]
        allowed, retry_after = ratelimit.check_rate_limit(ip, start + 2.0)
        assert not allowed and retry_after == 8
        assert ratelimit.check_rate_limit(ip, start + 10.5)[0]
    finally:
        _cleanup_ip(ip)


def test_rate_limit_local_fallback(monkeypatch):
    ip = "10.250.250.251"
    _cleanup_ip(ip)

    def boom(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "_check_redis", boom)
    monkeypatch.setattr(ratelimit, "_redis_down_until", 0.0)
    try:
        start = 2_000_000.0
        for i in range(100):
            assert ratelimit.check_rate_limit(ip, start + i * 0.01)[0]
        allowed, retry_after = ratelimit.check_rate_limit(ip, start + 1.0)
        assert not allowed and retry_after == 9
        assert ratelimit.check_rate_limit(ip, start + 11.0)[0]
    finally:
        _cleanup_ip(ip)
