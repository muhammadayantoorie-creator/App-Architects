"""Test harness: the real FastAPI app in-process, a throwaway SQLite DB and fake Redis.

Set TEST_DATABASE_URL / TEST_REDIS_URL to run the same tests against PostgreSQL / Redis.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_tmp = pathlib.Path(tempfile.mkdtemp(prefix="nascon-tests-"))
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{(_tmp / 'test.db').as_posix()}")
os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "fakeredis://")
# Always the test salt (compose may pass DAY1_SALT set-but-empty); tests sign with this value.
os.environ["DAY1_SALT"] = os.getenv("TEST_DAY1_SALT", "test-salt")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def reset(client: TestClient) -> dict:
    """Fresh baseline before the test (same call the grader makes)."""
    r = client.post("/audit/v1/reset", json={})
    assert r.status_code == 200, r.text
    return r.json()


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}, body
    assert body["error"]["code"] == code, body
    assert isinstance(body["error"]["details"], dict)
    return body["error"]
