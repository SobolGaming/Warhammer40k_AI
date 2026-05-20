from __future__ import annotations

import hashlib
import json
import random
import weakref
from typing import Any


_STATE_MARKER = "RandomSourceStateV2"
_SYSTEM_RANDOM = random.SystemRandom()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted((_json_safe(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=True))
    entity_id = getattr(value, "id", None)
    if entity_id is not None:
        return {"type": type(value).__name__, "id": str(entity_id)}
    name = getattr(value, "name", None)
    if name is not None:
        return {"type": type(value).__name__, "name": str(name)}
    return {"type": type(value).__name__}


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class RandomSource:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random()
        self._base_seed: Any = None
        self._branch_counters: dict[str, int] = {}
        self._branch_mode = True
        self._game_ref: weakref.ReferenceType[object] | None = None
        self.seed(seed)

    def attach_game(self, game: object | None) -> None:
        self._game_ref = weakref.ref(game) if game is not None else None

    def seed(self, seed: int | None) -> None:
        self._base_seed = _SYSTEM_RANDOM.getrandbits(256) if seed is None else seed
        self._branch_counters.clear()
        self._rng.seed(self._base_seed)

    def random(self, *, context: Any | None = None) -> float:
        rng = self._rng_for("random", (), context=context)
        return rng.random()

    def randint(self, a: int, b: int, *, context: Any | None = None) -> int:
        rng = self._rng_for("randint", (int(a), int(b)), context=context)
        return rng.randint(a, b)

    def randrange(self, *args: int, context: Any | None = None) -> int:
        rng = self._rng_for("randrange", tuple(int(arg) for arg in args), context=context)
        return rng.randrange(*args)

    def uniform(self, a: float, b: float, *, context: Any | None = None) -> float:
        rng = self._rng_for("uniform", (float(a), float(b)), context=context)
        return rng.uniform(a, b)

    def choice(self, seq, *, context: Any | None = None):
        if not self._use_branch_mode():
            return self._rng.choice(seq)
        if len(seq) <= 0:
            raise IndexError("Cannot choose from an empty sequence.")
        rng = self._rng_for("choice", (len(seq),), context=context)
        return seq[rng.randrange(len(seq))]

    def sample(self, population, k: int, *, context: Any | None = None):
        rng = self._rng_for("sample", (len(population), int(k)), context=context)
        return rng.sample(population, k)

    def shuffle(self, x, *, context: Any | None = None) -> None:
        rng = self._rng_for("shuffle", (len(x),), context=context)
        rng.shuffle(x)

    def getstate(self) -> Any:
        return (
            _STATE_MARKER,
            self._rng.getstate(),
            self._base_seed,
            dict(self._branch_counters),
            bool(self._branch_mode),
        )

    def setstate(self, state: Any) -> None:
        if isinstance(state, (list, tuple)) and len(state) == 5 and state[0] == _STATE_MARKER:
            self._rng.setstate(state[1])
            self._base_seed = state[2]
            self._branch_counters = {str(k): int(v) for k, v in dict(state[3] or {}).items()}
            self._branch_mode = bool(state[4])
            return
        self._rng.setstate(state)
        self._base_seed = "legacy-random-state"
        self._branch_counters.clear()

    def _attached_game(self) -> object | None:
        if self._game_ref is None:
            return None
        return self._game_ref()

    def _use_branch_mode(self) -> bool:
        return bool(self._branch_mode) and self._attached_game() is not None

    def _history_hash(self) -> str:
        game = self._attached_game()
        if game is None:
            return "detached"
        event_log = getattr(game, "event_log", None)
        if event_log is None:
            return "no_event_log"
        compute_history_hash = getattr(event_log, "compute_history_hash", None)
        if callable(compute_history_hash):
            return str(compute_history_hash(normalize_ids=True))
        compute_hash = getattr(event_log, "compute_hash", None)
        if callable(compute_hash):
            return str(compute_hash(normalize_ids=True))
        return "unhashable_event_log"

    def _rng_for(self, op: str, args: tuple[Any, ...], *, context: Any | None) -> random.Random:
        if not self._use_branch_mode():
            return self._rng
        history_hash = self._history_hash()
        counter_material = {
            "op": str(op),
            "args": list(args),
            "context": _json_safe(context),
        }
        counter_key = hashlib.sha256(_canonical_json(counter_material).encode("utf-8")).hexdigest()
        counter = int(self._branch_counters.get(counter_key, 0))
        self._branch_counters[counter_key] = counter + 1
        seed_material = {
            "base_seed": _json_safe(self._base_seed),
            "history_hash": history_hash,
            "op": str(op),
            "args": list(args),
            "context": _json_safe(context),
            "counter": counter,
        }
        seed = int(hashlib.sha256(_canonical_json(seed_material).encode("utf-8")).hexdigest(), 16)
        return random.Random(seed)
