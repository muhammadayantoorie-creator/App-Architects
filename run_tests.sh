#!/usr/bin/env sh
# Runs the backend unit tests in-process (SQLite + fake Redis by default; set
# TEST_DATABASE_URL / TEST_REDIS_URL to use real services) and writes coverage.
set -eu
cd "$(dirname "$0")"
python -m pytest tests -q --cov=backend --cov-report=term --cov-report=json:coverage_raw.json "$@"
