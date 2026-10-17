"""Domain-event worker: consumes the orders.events Redis stream with a consumer group."""

from __future__ import annotations

import logging
import os
import socket
import time

import redis

STREAM = "orders.events"
GROUP = "order-workers"

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
log = logging.getLogger("worker")


def _connect() -> redis.Redis:
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_timeout=10,
        socket_connect_timeout=5,
        decode_responses=True,
    )


def _ensure_group(client: redis.Redis) -> None:
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def run() -> None:
    consumer = f"{socket.gethostname()}-{os.getpid()}"
    client: redis.Redis | None = None
    while True:
        try:
            if client is None:
                client = _connect()
                _ensure_group(client)
                log.info("listening on %s as %s/%s", STREAM, GROUP, consumer)
            batches = client.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=50, block=5000)
            for _stream, messages in batches or []:
                for message_id, fields in messages:
                    log.info("event %s %s", message_id, fields)
                    client.xack(STREAM, GROUP, message_id)
        except redis.RedisError as exc:
            log.warning("redis unavailable (%s); retrying", exc)
            client = None
            time.sleep(2)


if __name__ == "__main__":
    run()
