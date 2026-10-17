# NaSCon '26 Backend

Backend platform for the NaSCon '26 multi-sport league and club operations app.

> Current state: bootstrap phase. Baseline seed hooks, audit endpoints, and the
> worker are still being implemented; `/health` will report ready after the
> baseline seeding code is in place.

## Run

Set `DAY1_SALT` to the salt supplied for your team, then start the services:

```sh
DAY1_SALT=your-team-salt docker compose up -d --build
```

The API listens at `http://localhost:8080`. Check readiness with `GET /health`.
Do not commit the real `DAY1_SALT`; `.env.example` contains a placeholder.

## Demo accounts

All demo accounts use the password `Nascon@26`:

| Role | Email |
| --- | --- |
| Platform Super-Admin | `admin@nascon.test` |
| League Organizer | `organizer@nascon.test` |
| Club Manager | `manager@nascon.test` |
| Player | `player@nascon.test` |
| General Viewer | `viewer@nascon.test` |

## Tests

Run `./run_tests.sh`.
