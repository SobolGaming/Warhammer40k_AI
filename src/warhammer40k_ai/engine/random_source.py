from __future__ import annotations

import random
from typing import Any


class RandomSource:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def seed(self, seed: int | None) -> None:
        self._rng.seed(seed)

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def randrange(self, *args: int) -> int:
        return self._rng.randrange(*args)

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def choice(self, seq):
        return self._rng.choice(seq)

    def sample(self, population, k: int):
        return self._rng.sample(population, k)

    def shuffle(self, x) -> None:
        self._rng.shuffle(x)

    def getstate(self) -> Any:
        return self._rng.getstate()

    def setstate(self, state: Any) -> None:
        self._rng.setstate(state)
