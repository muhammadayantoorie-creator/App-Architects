import base64
import json
import time

import jwt
import pytest

from backend.core.auth import _secret
from tests.conftest import assert_error

ROLES = ["super_admin", "league_organizer", "club_manager", "player", "viewer"]

# (method, path template, context key or None, expected per role in ROLES order)
MATRIX = [
    ("POST", "/audit/v1/rbac/tenants", None, "ADDDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "own_league_id", "AADDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "other_league_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/leagues/{}/fixtures", "foreign_league_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "own_club_id", "ADADD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "other_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/roster", "foreign_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "own_club_id", "ADADD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "other_club_id", "ADDDD"),
    ("POST", "/audit/v1/rbac/clubs/{}/products", "foreign_club_id", "ADDDD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "own_player_id", "ADAAD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "other_player_id", "ADDDD"),
    ("PATCH", "/audit/v1/rbac/players/{}", "foreign_player_id", "ADDDD"),
    ("GET", "/audit/v1/rbac/clubs/{}", "own_club_id", "AAAAA"),
    ("GET", "/audit/v1/rbac/clubs/{}", "other_club_id", "AAAAA"),
    ("GET", "/audit/v1/rbac/clubs/{}", "foreign_club_id", "ADDDD"),
    ("GET", "/audit/v1/rbac/platform/config", None, "ADDDD"),
]

CASES = [
    pytest.param(method, path, key, role, expected[i], id=f"{method}-{path}-{key}-{role}")
    for method, path, key, expected in MATRIX
    for i, role in enumerate(ROLES)
]


@pytest.fixture(scope="module")
def matrix(client):
    r = client.post("/audit/v1/reset", json={})
    assert r.status_code == 200
    r = client.post("/audit/v1/rbac-matrix")
    assert r.status_code == 200, r.text
    return r.json()


def _call(client, method, path, token=None, json_body=None):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    if method == "GET":
        return client.get(path, headers=headers)
    return client.request(method, path, headers=headers, json=json_body if json_body is not None else {})


def test_rbac_matrix_shape(matrix):
    assert set(matrix) == {"tokens", "context"}
    assert set(matrix["tokens"]) == set(ROLES)
    assert matrix["context"] == {
        "tenant_id": "tenant-alpha",
        "foreign_tenant_id": "tenant-beta",
        "own_league_id": "league-alpha-1",
        "other_league_id": "league-alpha-2",
        "foreign_league_id": "league-beta-1",
        "own_club_id": "club-alpha-1",
        "other_club_id": "club-alpha-2",
        "foreign_club_id": "club-beta-1",
        "own_player_id": "player-alpha-1",
        "other_player_id": "player-alpha-2",
        "foreign_player_id": "player-beta-1",
    }
    for role, token in matrix["tokens"].items():
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"
        claims = jwt.decode(token, options={"verify_signature": False})
        assert claims["role"] == role
        assert claims["exp"] - claims["iat"] >= 3600
        if role != "super_admin":
            assert claims["tenant_id"] == "tenant-alpha"


@pytest.mark.parametrize("method,path,key,role,expected", CASES)
def test_rbac_matrix_cell(client, matrix, method, path, key, role, expected):
    url = path.format(matrix["context"][key]) if key else path
    r = _call(client, method, url, matrix["tokens"][role])
    if expected == "A":
        assert r.status_code == 200, r.text
        assert r.json() == {"authorized": True}
    else:
        assert_error(r, 403, "FORBIDDEN")


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/audit/v1/rbac/tenants"),
        ("POST", "/audit/v1/rbac/leagues/league-alpha-1/fixtures"),
        ("POST", "/audit/v1/rbac/clubs/club-alpha-1/roster"),
        ("POST", "/audit/v1/rbac/clubs/club-alpha-1/products"),
        ("PATCH", "/audit/v1/rbac/players/player-alpha-1"),
        ("GET", "/audit/v1/rbac/clubs/club-alpha-1"),
        ("GET", "/audit/v1/rbac/platform/config"),
    ],
)
def test_probe_without_token_is_401(client, matrix, method, path):
    assert_error(_call(client, method, path), 401, "UNAUTHENTICATED")


def test_probe_ignores_body(client, matrix):
    token = matrix["tokens"]["super_admin"]
    r = client.post(
        "/audit/v1/rbac/tenants",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        content=b"{not json",
    )
    assert r.status_code == 200, r.text
    r = client.patch(
        "/audit/v1/rbac/players/player-alpha-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text


def test_non_bearer_scheme_is_401(client, matrix):
    token = matrix["tokens"]["super_admin"]
    r = client.get("/audit/v1/rbac/platform/config", headers={"Authorization": f"Token {token}"})
    assert_error(r, 401, "UNAUTHENTICATED")
    r = client.get("/audit/v1/rbac/platform/config", headers={"Authorization": "Bearer garbage"})
    assert_error(r, 401, "UNAUTHENTICATED")


def test_tampered_signature_is_401(client, matrix):
    token = matrix["tokens"]["super_admin"]
    head, payload, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    r = _call(client, "GET", "/audit/v1/rbac/platform/config", f"{head}.{payload}.{flipped}")
    assert_error(r, 401, "UNAUTHENTICATED")


def test_tampered_payload_is_401(client, matrix):
    token = matrix["tokens"]["viewer"]
    head, payload, sig = token.split(".")
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["role"] = "super_admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    r = _call(client, "GET", "/audit/v1/rbac/platform/config", f"{head}.{forged}.{sig}")
    assert_error(r, 401, "UNAUTHENTICATED")


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def test_alg_none_is_401(client, matrix):
    now = int(time.time())
    claims = {"sub": "user-admin", "role": "super_admin", "tenant_id": None, "iat": now, "exp": now + 3600}
    for alg in ("none", "None", "NONE"):
        token = f"{_b64({'alg': alg, 'typ': 'JWT'})}.{_b64(claims)}."
        r = _call(client, "GET", "/audit/v1/rbac/platform/config", token)
        assert_error(r, 401, "UNAUTHENTICATED")


def test_expired_token_is_401(client, matrix):
    now = int(time.time())
    claims = {"sub": "user-admin", "role": "super_admin", "tenant_id": None, "iat": now - 7200, "exp": now - 60}
    token = jwt.encode(claims, _secret(), algorithm="HS256")
    assert_error(_call(client, "GET", "/audit/v1/rbac/platform/config", token), 401, "UNAUTHENTICATED")


def test_token_without_exp_is_401(client, matrix):
    token = jwt.encode({"sub": "user-admin", "role": "super_admin"}, _secret(), algorithm="HS256")
    assert_error(_call(client, "GET", "/audit/v1/rbac/platform/config", token), 401, "UNAUTHENTICATED")


def test_wrong_secret_is_401(client, matrix):
    now = int(time.time())
    token = jwt.encode({"sub": "user-admin", "role": "super_admin", "exp": now + 3600}, "other-secret-value-0123456789abcdef", algorithm="HS256")
    assert_error(_call(client, "GET", "/audit/v1/rbac/platform/config", token), 401, "UNAUTHENTICATED")


def test_unknown_ids_are_404(client, matrix):
    admin = matrix["tokens"]["super_admin"]
    assert_error(_call(client, "POST", "/audit/v1/rbac/leagues/nope/fixtures", admin), 404, "LEAGUE_NOT_FOUND")
    assert_error(_call(client, "PATCH", "/audit/v1/rbac/players/nope", admin), 404, "PLAYER_NOT_FOUND")
    assert_error(_call(client, "POST", "/audit/v1/rbac/clubs/nope/roster", admin), 404, "NOT_FOUND")
    assert_error(_call(client, "GET", "/audit/v1/rbac/clubs/nope", matrix["tokens"]["viewer"]), 404, "NOT_FOUND")


def test_matrix_tokens_survive_reset(client, matrix):
    r = client.post("/audit/v1/reset", json={})
    assert r.status_code == 200
    r = _call(client, "POST", "/audit/v1/rbac/clubs/club-alpha-1/roster", matrix["tokens"]["club_manager"])
    assert r.status_code == 200, r.text


def test_rbac_leagues_seeded(client, reset):
    from backend.core.db import SessionLocal
    from backend.modules.leagues.models import League

    with SessionLocal() as session:
        league = session.get(League, "league-alpha-1")
        assert league is not None
        assert league.tenant_id == "tenant-alpha"
        assert league.points == {"win": 3, "draw": 1, "loss": 0}
        assert league.qualification_spots == 2
        assert league.lots_seed == 42
        assert league.tie_break_order[-1] == "draw_lots"
        assert session.get(League, "league-beta-1").tenant_id == "tenant-beta"
