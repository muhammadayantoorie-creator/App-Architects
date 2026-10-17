# Huddle — NaSCon '26 multi-sport league & club platform

Huddle is a multi-tenant sports league and club-operations platform: data-driven sports (any
sport added as JSON), fixture and bracket generation, an append-only signed scoring engine,
standings with full tie-break rules, club rosters with transfers and loans, a concurrency-safe
merchandise store with signed PDF receipts, five-role RBAC, and an offline-first Android app.

## Stack

- API: Python 3.11, FastAPI, SQLAlchemy 2 (`backend/`)
- Database: PostgreSQL 16 · Cache / rate limiting / queue: Redis 7 (Redis Streams `orders.events`)
- Worker: `backend/worker/main.py` (consumes domain events)
- Mobile: Flutter (Android), `mobile/`
- Everything self-hosted with Docker Compose; images: `postgres:16-alpine`, `redis:7-alpine`,
  `python:3.11-slim`.

## Run

```sh
DAY1_SALT=<your-team-salt> docker compose up -d --build
```

The API listens on **http://localhost:8080**. `GET /health` returns `{"status":"ok"}` once the
database is reachable and the baseline is seeded (seeding runs automatically at startup and on
`POST /audit/v1/reset`). Never commit the real salt.

### Environment variables (see `.env.example`)

| Variable | Purpose |
|---|---|
| `DAY1_SALT` | HMAC key for event and receipt signatures (read only from the environment) |
| `DATABASE_URL` | SQLAlchemy URL (compose: `postgresql+psycopg://app:app@db:5432/app`) |
| `REDIS_URL` | Redis URL (compose: `redis://redis:6379/0`) |
| `JWT_SECRET` | Optional JWT signing key; defaults to a key derived from `DAY1_SALT` |

## Demo accounts

All demo accounts use the password `Nascon@26` and exist after every startup and reset:

| Role | Email |
| --- | --- |
| Platform Super-Admin | `admin@nascon.test` |
| League Organizer (owns `league-alpha-1`) | `organizer@nascon.test` |
| Club Manager (owns `club-alpha-1`) | `manager@nascon.test` |
| Player (`player-alpha-1`) | `player@nascon.test` |
| General Viewer | `viewer@nascon.test` |

## Tests

```sh
pip install -r requirements.txt
./run_tests.sh
```

Runs the full pytest suite against the real app in-process (SQLite + fake Redis by default; set
`TEST_DATABASE_URL` / `TEST_REDIS_URL` to use PostgreSQL / Redis) and writes coverage to
`coverage_raw.json`. Per-area figures are in `COVERAGE.json`; requirement mapping in
`TRACEABILITY.md`.

## Mobile app

- Installable APK: `mobile/release/app-release.apk` (Android 10+).
- Set the server: on the sign-in screen tap the **gear** icon → **Server URL** →
  `http://<laptop LAN IP>:8080` (emulator: `http://10.0.2.2:8080`) → **Test connection** → **Save**.
  Phone and laptop must be on the same Wi-Fi / hotspot.
- Sign in with any demo account (quick-login chips). Details: `mobile/README.md`.

## API surface

- Grader interface `/audit/v1/*` (spec Section 5): reset, sports, fixtures, leagues, events, score,
  standings, roster setup/transfer/history, checkout, inventory, rbac-matrix + 7 probes, offline-sync.
- App routes `/api/v1/*` (Bearer JWT, rate limited 100 req / 10 s per IP): auth/login, me, ping,
  leagues, fixtures, standings, matches, sports, clubs, player history, store products, checkout,
  events, roster actions, add player, offline-sync, pinned product, live (SSE).
