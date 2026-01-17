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

    def getstate(self) -> Any:
        return self._rng.getstate()

    def setstate(self, state: Any) -> None:
        self._rng.setstate(state)
