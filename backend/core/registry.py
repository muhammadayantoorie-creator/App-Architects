"""Ordered reset hook registry shared by feature modules."""

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

ResetHook = Callable[[Session, int, dict[str, Any]], None]
_hooks: list[tuple[int, ResetHook]] = []


def register_reset(order: int, fn: ResetHook) -> None:
    _hooks.append((order, fn))
    _hooks.sort(key=lambda item: item[0])


def run_reset_hooks(session: Session, seed: int, stock: dict[str, Any]) -> None:
    for _, hook in _hooks:
        hook(session, seed, stock)


def reset_hooks() -> tuple[tuple[int, ResetHook], ...]:
    return tuple(_hooks)
