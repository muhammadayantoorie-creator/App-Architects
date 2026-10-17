"""Canonical JSON and HMAC helpers used by audit records."""

import hashlib
import hmac
import json
import os
from typing import Any


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(salt: str, id_: str, payload_obj: Any) -> str:
    msg = (id_ + "|" + canonical(payload_obj)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def lots_key(seed: int, league_id: str, team_id: str) -> str:
    return hashlib.sha256(
        f"{seed}|{league_id}|{team_id}".encode("utf-8")
    ).hexdigest()


def salt() -> str:
    return os.environ["DAY1_SALT"]
