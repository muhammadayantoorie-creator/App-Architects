#!/usr/bin/env sh
# Runs the backend test suite and writes coverage (coverage_raw.json).
# The tests start the real FastAPI app in-process on SQLite + fake Redis, so no database or
# Redis server is needed. Uses local Python if the requirements are installed; otherwise runs
# inside the API image via Docker Compose (only Docker required).
set -eu
cd "$(dirname "$0")"

ARGS="tests -q -p no:cacheprovider --cov=backend --cov-report=term --cov-report=json:coverage_raw.json"
CHECK="import pytest, pytest_cov, fastapi, sqlalchemy, fakeredis, jwt, reportlab"

for PY in python3 python; do
  if command -v "$PY" >/dev/null 2>&1 && "$PY" -c "$CHECK" >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    exec "$PY" -m pytest $ARGS "$@"
  fi
done

if command -v docker >/dev/null 2>&1; then
  echo "Local Python deps not found; running tests inside the api image (docker compose run)..." >&2
  # shellcheck disable=SC2086
  exec docker compose run --rm --no-deps -T \
    -v "$(pwd):/app" -w /app \
    -e DAY1_SALT=test-salt \
    api python -m pytest $ARGS "$@"
fi

echo "run_tests.sh needs Docker, or Python 3.11 with: pip install -r requirements.txt" >&2
exit 1
