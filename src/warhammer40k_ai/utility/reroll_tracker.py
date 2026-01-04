from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RerollTracker:
    next_id: int = 1
    used: dict[int, bool] = field(default_factory=dict)
    results: dict[int, Any] = field(default_factory=dict)

    def new_roll_id(self) -> int:
        roll_id = int(self.next_id)
        self.next_id += 1
        return roll_id

    def is_used(self, roll_id: int) -> bool:
        return bool(self.used.get(int(roll_id), False))

    def mark_used(self, roll_id: int, result: Any) -> None:
        rid = int(roll_id)
        self.used[rid] = True
        self.results[rid] = result

    def get_result(self, roll_id: int) -> Any:
        return self.results.get(int(roll_id))

    def wrap(self, roll_id: int, fn: Callable[[], Any]) -> Callable[[], Any]:
        def _wrapped():
            if self.is_used(roll_id):
                return self.get_result(roll_id)
            result = fn()
            self.mark_used(roll_id, result)
            return result
        return _wrapped


def get_reroll_tracker(game) -> RerollTracker | None:
    if game is None:
        return None
    tracker = getattr(game, "_reroll_tracker", None)
    if tracker is None:
        tracker = RerollTracker()
        setattr(game, "_reroll_tracker", tracker)
    return tracker


def prepare_reroll_event(
    game,
    reroll_fn: Callable[[], Any],
    *,
    reroll_used: bool = False,
    used_result: Any = None,
) -> tuple[int | None, Callable[[], Any], bool]:
    tracker = get_reroll_tracker(game)
    roll_id = None
    reroll_cb = reroll_fn
    locked = bool(reroll_used)
    if tracker is not None:
        roll_id = tracker.new_roll_id()
        reroll_cb = tracker.wrap(roll_id, reroll_fn)
        if reroll_used:
            tracker.mark_used(roll_id, used_result)
        locked = locked or tracker.is_used(roll_id)
    return roll_id, reroll_cb, locked
