# Traceability — requirements → source → tests

Tests run with `./run_tests.sh` (pytest + pytest-cov, in-process app on SQLite + fake Redis by
default; set `TEST_DATABASE_URL` / `TEST_REDIS_URL` for PostgreSQL / Redis). Coverage per area is in
`COVERAGE.json` (area → source prefixes listed in the last section).

| ID | Requirement | Source files | Tests | Status |
|---|---|---|---|---|
| FR-1.1 | Multi-sport taxonomy as data, mystery sport via JSON, three scoring models, event-sourced scoring with signed compensating events | `backend/modules/sports/` (service, seed), `backend/modules/events/` (service, router), `backend/core/signing.py` | `tests/test_sports.py`, `tests/test_events.py` | Implemented |
| FR-1.2 | League setup scoped to sport/tenant (single-stage leagues with points, tie-break order, qualification) | `backend/modules/leagues/`, `backend/modules/org/seed.py` (RBAC leagues), `backend/modules/demo/` (demo league) | `tests/test_leagues.py`, `tests/test_rbac.py` | Partial — single-stage leagues; multi-division promotion/relegation and hybrid group→knockout are not modelled as entities (brackets via FR-1.3) |
| FR-1.3 | Fixture generation: round-robin (circle method, byes, legs, withdrawals), Swiss (Buchholz, minimum-difference rematch-free pairing, NO_VALID_PAIRING), single and double elimination (exact seeding, byes, results, third place, bracket reset); match status state machine | `backend/fixtures/round_robin.py`, `swiss.py`, `single_elim.py`, `double_elim.py`, `router.py`; state machine in `backend/modules/events/service.py` | `tests/test_fixtures.py`, `tests/test_events.py` | Implemented (generation + state machine). Manual rescheduling conflict detection: not implemented |
| FR-1.4 | Standings recomputed from event logs: configurable points, tie-break chain incl. 3-way H2H mini-league and drawing of lots, H2H matrix, differentials (goal/point, NRR, map), clinched/eliminated/still_possible | `backend/modules/standings/service.py`, `router.py` | `tests/test_standings.py` | Implemented |
| FR-2.1 | Club profiles (venue coordinates, socials, staff, roster) and white-label tenants (name, logo, colours) with tenant isolation | `backend/modules/org/` (models, seed, router), `backend/modules/tenants/`, `backend/modules/app_api/router.py` (`/api/v1/clubs/{id}`, `/api/v1/me`) | `tests/test_auth.py`, `tests/test_app_api.py` | Implemented (historical season statistics not modelled) |
| FR-2.2 | Roster: add, transfer, loan with automatic return, release; transfer windows, squad size, min positions, roles, single registration; immutable audit trail | `backend/modules/roster/` (models, service, router, seed), `backend/modules/app_api/router.py` (add player, `/api/v1/roster/actions`) | `tests/test_roster.py`, `tests/test_app_api.py` | Implemented |
| FR-2.3 | Store: catalogue with variants, discount code, concurrency-safe inventory, mock gateway (authorize/capture/failure), paid orders, signed server-side PDF receipt, order events to the internal queue, pinned product on match pages | `backend/modules/store/` (models, seed, service, pdf, router), `backend/worker/main.py` (consumes `orders.events`), `backend/modules/app_api/router.py` (pinned product, live) | `tests/test_store.py`, `tests/test_app_api.py` | Implemented (scheduled price changes and post-payment order states Packed/Shipped/Delivered/Refunded not implemented) |
| FR-5.1 | Five-tier RBAC with tenant isolation, policy enforced per route, negative tests for every role boundary | `backend/core/auth.py`, `backend/modules/rbac/router.py`, `backend/modules/app_api/router.py` | `tests/test_rbac.py` (full 5.13 matrix), `tests/test_auth.py`, `tests/test_app_api.py` | Implemented |
| NFR-3 | Concurrency correctness: 20 simultaneous buyers on the last unit → exactly one order, no negative stock | `backend/modules/store/service.py` (conditional `UPDATE … WHERE stock >= q` reservation, unique `order_id`) | `tests/test_store.py` (20 threads behind a barrier) | Implemented |
| NFR-4 | Offline tolerance: mobile SQLite cache, persistent outbox in 5.14 format, conflict-handling sync | Mobile: `mobile/lib/core/db.dart`, `mobile/lib/data/repository.dart`, `mobile/lib/data/sync/outbox.dart`, `mobile/lib/data/app_state.dart`, `mobile/lib/ui/screens/outbox.dart`. Server: `backend/modules/offline_sync/` | `tests/test_offline_sync.py`, `tests/test_app_api.py` | Implemented |
| NFR-5 | Security: secure token storage (Keystore), JWT verification (alg:none/tampered/expired → 401), RBAC, rate limiting on `/api/v1/*`, input validation, 1 MB body limit | `mobile/lib/core/secure_store.dart`, `backend/core/auth.py`, `backend/core/ratelimit.py`, `backend/core/middleware.py`, `backend/core/errors.py`, `backend/core/ids.py` | `tests/test_auth.py`, `tests/test_rbac.py`, `tests/test_startup.py`, `tests/test_sports.py` (SQL-injection id) | Implemented |
| NFR-7 | Reproducibility: `docker compose up -d --build` brings up API, PostgreSQL, Redis and worker; seeds the baseline at startup; `/health` 200 only when seeded | `docker-compose.yml`, `Dockerfile`, `backend/app/main.py`, `backend/modules/reset/router.py`, `backend/core/registry.py` | `tests/test_startup.py` | Implemented |

## COVERAGE.json areas

| Area | Source prefixes |
|---|---|
| fixtures | `backend/fixtures/` |
| scoring | `backend/modules/events/`, `backend/modules/sports/` |
| standings | `backend/modules/standings/`, `backend/modules/leagues/` |
| store | `backend/modules/store/` |
| roster | `backend/modules/roster/`, `backend/modules/offline_sync/` |
| rbac | `backend/modules/rbac/`, `backend/modules/auth/`, `backend/core/auth.py`, `backend/core/ratelimit.py` |
