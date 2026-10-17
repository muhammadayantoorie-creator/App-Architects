"""Ordered reset hook registry shared by feature modules."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.core.db import Base

ResetHook = Callable[[Session, int, dict[str, Any]], None]
_hooks: list[tuple[int, ResetHook]] = []


def register_reset(order: int, fn: ResetHook) -> None:
    _hooks.append((order, fn))
    _hooks.sort(key=lambda item: item[0])


def run_reset_hooks(session: Session, seed: int, stock: dict[str, Any]) -> None:
    for _, hook in _hooks:
        hook(session, seed, stock)


def clear_database(session: Session) -> None:
    """Delete registered model rows in reverse dependency order."""
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))


def reset_hooks() -> tuple[tuple[int, ResetHook], ...]:
    return tuple(_hooks)
