from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_active_game: ContextVar[object | None] = ContextVar("active_game", default=None)
_roll_context: ContextVar[str | None] = ContextVar("roll_context", default=None)


def get_active_game() -> object | None:
    return _active_game.get()


@contextmanager
def game_context(game: object | None) -> Iterator[object | None]:
    token = _active_game.set(game)
    try:
        yield game
    finally:
        _active_game.reset(token)


def get_roll_context() -> str | None:
    return _roll_context.get()


@contextmanager
def roll_context(context: str | None) -> Iterator[str | None]:
    token = _roll_context.set(context)
    try:
        yield context
    finally:
        _roll_context.reset(token)
