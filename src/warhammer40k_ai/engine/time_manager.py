from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable


DEFAULT_DECISION_CAPS_MS: dict[str, int] = {
    "MOVE_UNIT": 220,
    "SELECT_TARGETS": 140,
    "PLAY_STRATAGEM": 60,
    "DECLARE_CHARGE": 120,
}

DEFAULT_TIER_MULTIPLIERS: dict[str, float] = {
    "P0": 1.8,
    "P1": 1.0,
    "P2": 0.5,
}


@dataclass(frozen=True)
class TimeBudgetPolicy:
    decision_caps_ms: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DECISION_CAPS_MS))
    tier_multipliers: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TIER_MULTIPLIERS))
    default_cap_ms: int = 150

    def cap_for(self, decision_type: str) -> int:
        dtype = str(decision_type or "").strip().upper()
        value = self.decision_caps_ms.get(dtype, self.default_cap_ms)
        return max(1, int(value))

    def multiplier_for(self, compute_tier: str | None) -> float:
        tier = str(compute_tier or "P1").strip().upper()
        value = self.tier_multipliers.get(tier, self.tier_multipliers["P1"])
        return max(0.1, float(value))


class TimeManager:
    def __init__(self, policy: TimeBudgetPolicy | None = None) -> None:
        self.policy = policy if policy is not None else TimeBudgetPolicy()

    def get_time_budget_ms(self, decision_type: str, *, compute_tier: str | None = None) -> int:
        cap = self.policy.cap_for(decision_type)
        multiplier = self.policy.multiplier_for(compute_tier)
        return max(1, int(round(float(cap) * float(multiplier))))

    def decorate_context(self, decision_type: str, context: dict[str, Any]) -> dict[str, Any]:
        ctx = dict(context or {})
        compute_tier = str(ctx.get("compute_tier", "P1") or "P1").upper()
        if "compute_tier" not in ctx:
            ctx["compute_tier"] = compute_tier
        if "time_budget_ms" not in ctx:
            ctx["time_budget_ms"] = self.get_time_budget_ms(decision_type, compute_tier=compute_tier)
        return ctx

    def run_with_time_budget(
        self,
        *,
        budget_ms: int,
        action: Callable[[float], Any],
        fallback: Callable[[], Any],
    ) -> tuple[Any, bool, int]:
        start = time.perf_counter()
        deadline = start + (max(0, int(budget_ms)) / 1000.0)
        value = action(deadline)
        elapsed_ms = int(round((time.perf_counter() - start) * 1000.0))
        if elapsed_ms > int(budget_ms):
            return fallback(), True, elapsed_ms
        return value, False, elapsed_ms
