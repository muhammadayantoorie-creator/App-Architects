#!/usr/bin/env sh
set -eu
pytest --cov=backend --cov-report=json:coverage_raw.json -q
