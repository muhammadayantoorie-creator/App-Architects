"""The /api/v1 routes the mobile app calls (FRONTEND contract), end to end."""

import pytest

from tests.conftest import assert_error

PASSWORD = "Nascon@26"


def _login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD},
                    headers={"X-Forwarded-For": f"10.9.0.{abs(hash(email)) % 200 + 1}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture
def org(client, reset):
    return _login(client, "organizer@nascon.test")


@pytest.fixture
def mgr(client, reset):
    return _login(client, "manager@nascon.test")


@pytest.fixture
def viewer(client, reset):
    return _login(client, "viewer@nascon.test")


def test_requires_token(client, reset):
    assert_error(client.get("/api/v1/leagues"), 401, "UNAUTHENTICATED")


def test_me_has_tenant_branding(client, mgr):
    me = client.get("/api/v1/me", headers=mgr).json()
    assert me["role"] == "club_manager" and me["club_id"] == "club-alpha-1"
    assert me["tenant"]["name"] == "Alpha Sports"
    assert me["tenant"]["primary_color"].startswith("#")


def test_league_fixtures_match_standings_flow(client, viewer):
    leagues = client.get("/api/v1/leagues", headers=viewer).json()["items"]
    assert leagues[0]["league_id"] == "demo-league-ui"
    assert all(l["tenant_id"] in (None, "tenant-alpha") for l in leagues)

    fx = client.get("/api/v1/leagues/demo-league-ui/fixtures", headers=viewer).json()
    rows = fx["fixtures"]
    assert len(rows) == 6
    for key in ("match_id", "home_team_id", "home_name", "away_team_id", "away_name",
                "scheduled_at", "status", "home_score", "away_score", "version"):
        assert key in rows[0]
    assert {r["status"] for r in rows} >= {"completed", "in_progress", "upcoming"}

    live = next(r for r in rows if r["status"] == "in_progress")
    m = client.get(f"/api/v1/matches/{live['match_id']}", headers=viewer).json()
    assert m["home"]["name"] and m["away"]["name"] and m["events"]
    assert "pinned_product" in m and "venue" in m

    st = client.get("/api/v1/leagues/demo-league-ui/standings", headers=viewer).json()
    assert st["table"] and st["team_names"]["club-alpha-1"] == "Alpha FC"

    sp = client.get(f"/api/v1/sports/{m['sport_id']}", headers=viewer).json()
    assert sp["scoring_events"]


def test_foreign_league_forbidden(client, viewer):
    assert_error(client.get("/api/v1/leagues/league-beta-1/fixtures", headers=viewer), 403, "FORBIDDEN")


def test_organizer_scores_live_match_viewer_cannot(client, org, viewer):
    rows = client.get("/api/v1/leagues/demo-league-ui/fixtures", headers=org).json()["fixtures"]
    live = next(r for r in rows if r["status"] == "in_progress")
    match = client.get(f"/api/v1/matches/{live['match_id']}", headers=org).json()
    event_type = next(iter(client.get(f"/api/v1/sports/{match['sport_id']}", headers=org).json()["scoring_events"]))
    body = {"event_id": "app-evt-1", "match_id": live["match_id"], "type": "score",
            "payload": {"team_id": live["home_team_id"], "event_type": event_type}}
    assert_error(client.post("/api/v1/events", json=body, headers=viewer), 403, "FORBIDDEN")
    r = client.post("/api/v1/events", json=body, headers=org)
    assert r.status_code == 201, r.text
    after = client.get(f"/api/v1/matches/{live['match_id']}", headers=org).json()
    assert after["home"]["score"] == match["home"]["score"] + 1


def test_club_profile_and_roster_action(client, mgr):
    club = client.get("/api/v1/clubs/club-alpha-1", headers=mgr).json()
    assert club["name"] == "Alpha FC" and club["home_venue"]["name"]
    assert len(club["staff"]) >= 3
    assert club["roster"] and club["destination_squads"]
    player = next(p for p in club["roster"] if p["position"] != "gk")
    body = {"request_id": "app-tr-1", "league_id": club["roster_league_id"], "player_id": player["player_id"],
            "type": "transfer", "from_squad_id": club["squad_id"],
            "to_squad_id": club["destination_squads"][0]["squad_id"], "effective_date": "2026-10-20",
            "loan_end_date": None, "reason": "Test", "requested_by": "user-manager"}
    r = client.post("/api/v1/roster/actions", json=body, headers=mgr)
    assert r.status_code == 201, r.text
    hist = client.get(f"/api/v1/players/{player['player_id']}/history", headers=mgr).json()
    assert hist["history"]


def test_store_and_checkout(client, mgr, viewer):
    items = client.get("/api/v1/store/products", headers=mgr).json()["items"]
    assert items[0]["product_id"] == "demo-prod-scarf"
    body = {"order_id": "app-ord-1", "customer_id": "user-manager",
            "items": [{"variant_id": "demo-var-scarf-std", "quantity": 1}],
            "discount_code": None, "payment": {"token": "tok_success"}}
    assert_error(client.post("/api/v1/checkout", json=body, headers=viewer), 403, "FORBIDDEN")
    r = client.post("/api/v1/checkout", json=body, headers=mgr)
    assert r.status_code == 201, r.text
    assert r.json()["receipt"]["pdf_base64"]


def test_store_app_routes_enforce_tenant_and_customer(client, mgr, org):
    from backend.core.db import SessionLocal
    from backend.modules.store.models import Product, Variant

    with SessionLocal.begin() as session:
        session.add(Product(product_id="beta-product", tenant_id="tenant-beta", name="Beta shirt",
                            category="apparel", description="Beta only", position=9))
        session.flush()
        session.add(Variant(variant_id="beta-variant", product_id="beta-product", label="M",
                            price_minor=10000, currency="PKR", stock=2, reserved=0, position=0))

    manager_items = client.get("/api/v1/store/products", headers=mgr).json()["items"]
    admin = _login(client, "admin@nascon.test")
    admin_items = client.get("/api/v1/store/products", headers=admin).json()["items"]
    assert "beta-product" not in {item["product_id"] for item in manager_items}
    assert "beta-product" in {item["product_id"] for item in admin_items}

    order = {"order_id": "tenant-checkout", "customer_id": "forged-customer",
             "items": [{"variant_id": "beta-variant", "quantity": 1}],
             "discount_code": None, "payment": {"token": "tok_success"}}
    assert_error(client.post("/api/v1/checkout", json=order, headers=mgr), 403, "FORBIDDEN")
    order["items"][0]["variant_id"] = "demo-var-scarf-std"
    paid = client.post("/api/v1/checkout", json=order, headers=mgr)
    assert paid.status_code == 201, paid.text
    assert paid.json()["receipt"]["payload"]["customer_id"] == "user-manager"

    assert_error(client.post("/api/v1/matches/demo-match-4/pinned-product",
                             json={"product_id": "beta-product"}, headers=org), 403, "FORBIDDEN")
    pin = client.post("/api/v1/matches/demo-match-4/pinned-product",
                      json={"product_id": "demo-prod-scarf"}, headers=org)
    assert pin.status_code == 200, pin.text
    detail = client.get("/api/v1/matches/demo-match-4", headers=mgr).json()
    assert detail["pinned_product"]["product_id"] == "demo-prod-scarf"


def test_offline_sync_via_app_route(client, org):
    rows = client.get("/api/v1/leagues/demo-league-ui/fixtures", headers=org).json()["fixtures"]
    live = next(r for r in rows if r["status"] == "in_progress")
    match = client.get(f"/api/v1/matches/{live['match_id']}", headers=org).json()
    event_type = next(iter(client.get(f"/api/v1/sports/{match['sport_id']}", headers=org).json()["scoring_events"]))
    body = {"device_id": "dev-app-1", "actions": [{
        "action_id": "a-app-1", "type": "score_event", "queued_at": "2026-10-17T11:00:00Z",
        "base_version": match["version"],
        "payload": {"event_id": "app-sync-evt-1", "match_id": live["match_id"], "type": "score",
                    "payload": {"team_id": live["home_team_id"], "event_type": event_type}}}]}
    r = client.post("/api/v1/offline-sync", json=body, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["status"] == "applied"
    again = client.post("/api/v1/offline-sync", json=body, headers=org).json()
    assert again["results"][0]["status"] == "duplicate"
