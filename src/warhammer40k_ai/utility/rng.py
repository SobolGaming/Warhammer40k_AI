from __future__ import annotations

import random
from typing import Iterable, Sequence, TypeVar

from .game_context import get_active_game

T = TypeVar("T")

_SYSTEM_RNG = random.SystemRandom()


def resolve_rng(game: object | None = None):
    if game is None:
        game = get_active_game()
    if game is not None:
        rng = getattr(game, "random_source", None)
        if rng is not None:
            return rng
    return _SYSTEM_RNG


def randint(a: int, b: int, *, game: object | None = None) -> int:
    return int(resolve_rng(game).randint(int(a), int(b)))


def uniform(a: float, b: float, *, game: object | None = None) -> float:
    rng = resolve_rng(game)
    if hasattr(rng, "uniform"):
        return float(rng.uniform(float(a), float(b)))
    return float(a) + (float(b) - float(a)) * float(rng.random())


def choice(seq: Sequence[T], *, game: object | None = None) -> T:
    return resolve_rng(game).choice(seq)


def sample(population: Sequence[T], k: int, *, game: object | None = None) -> list[T]:
    return list(resolve_rng(game).sample(population, int(k)))


def shuffle(items: list[T], *, game: object | None = None) -> None:
    resolve_rng(game).shuffle(items)
