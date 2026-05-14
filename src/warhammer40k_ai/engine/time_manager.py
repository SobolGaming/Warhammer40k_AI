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


DEFAULT_DECISION_WORK_CAPS: dict[str, int] = {
    "MOVE_UNIT": 900,
    "SELECT_TARGETS": 600,
    "PLAY_STRATAGEM": 250,
    "DECLARE_CHARGE": 500,
    "DECLARE_SHOTS": 1200,
    "SELECT_UNIT": 500,
    "RESERVES_ARRIVAL": 850,
}


@dataclass
class WorkBudget:
    unit_limit: int
    units_used: int = 0
    exhausted_category: str = ""

    def consume(self, units: int = 1, *, category: str = "generic") -> bool:
        amount = max(1, int(units))
        if self.exhausted:
            return False
        self.units_used += amount
        if self.units_used > self.unit_limit:
            self.exhausted_category = str(category or "generic")
            return False
        return True

    @property
    def exhausted(self) -> bool:
        return int(self.units_used) > int(self.unit_limit)

    def to_context(self) -> dict[str, Any]:
        return {
            "budget_mode": "work_units",
            "work_budget_units": int(max(0, self.unit_limit)),
            "work_units_used": int(max(0, self.units_used)),
            "work_budget_exhausted": bool(self.exhausted),
            "work_budget_exhausted_reason": str(self.exhausted_category or ""),
        }


@dataclass(frozen=True)
class TimeBudgetPolicy:
    decision_caps_ms: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DECISION_CAPS_MS))
    decision_work_caps: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DECISION_WORK_CAPS))
    tier_multipliers: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TIER_MULTIPLIERS))
    default_cap_ms: int = 150
    default_work_cap_units: int = 600

    def cap_for(self, decision_type: str) -> int:
        dtype = str(decision_type or "").strip().upper()
        value = self.decision_caps_ms.get(dtype, self.default_cap_ms)
        return max(1, int(value))

    def work_cap_for(self, decision_type: str) -> int:
        dtype = str(decision_type or "").strip().upper()
        value = self.decision_work_caps.get(dtype, self.default_work_cap_units)
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

    def get_work_budget_units(self, decision_type: str, *, compute_tier: str | None = None) -> int:
        cap = self.policy.work_cap_for(decision_type)
        multiplier = self.policy.multiplier_for(compute_tier)
        return max(1, int(round(float(cap) * float(multiplier))))

    def decorate_context(self, decision_type: str, context: dict[str, Any]) -> dict[str, Any]:
        ctx = dict(context or {})
        compute_tier = str(ctx.get("compute_tier", "P1") or "P1").upper()
        if "compute_tier" not in ctx:
            ctx["compute_tier"] = compute_tier
        if "time_budget_ms" not in ctx:
            ctx["time_budget_ms"] = self.get_time_budget_ms(decision_type, compute_tier=compute_tier)
        if "work_budget_units" not in ctx:
            ctx["work_budget_units"] = self.get_work_budget_units(decision_type, compute_tier=compute_tier)
        if "budget_mode" not in ctx:
            ctx["budget_mode"] = "work_units"
        return ctx

    def create_work_budget(
        self,
        decision_type: str,
        *,
        compute_tier: str | None = None,
        context: dict[str, Any] | None = None,
        fallback_units: int | None = None,
    ) -> WorkBudget:
        ctx = dict(context or {})
        raw_units = ctx.get("work_budget_units", None)
        if raw_units is None:
            units = (
                int(fallback_units)
                if fallback_units is not None
                else self.get_work_budget_units(decision_type, compute_tier=compute_tier or str(ctx.get("compute_tier", "P1") or "P1"))
            )
        else:
            units = int(raw_units)
        return WorkBudget(unit_limit=max(0, int(units)))

    def run_with_time_budget(
        self,
        *,
        budget_ms: int,
        action: Callable[[WorkBudget], Any],
        fallback: Callable[[], Any],
        work_budget: WorkBudget | None = None,
    ) -> tuple[Any, bool, int]:
        start = time.perf_counter()
        budget = work_budget if work_budget is not None else WorkBudget(unit_limit=max(0, int(budget_ms)))
        if not budget.consume(category="solver.invoke"):
            elapsed_ms = int(round((time.perf_counter() - start) * 1000.0))
            return fallback(), True, elapsed_ms
        value = action(budget)
        elapsed_ms = int(round((time.perf_counter() - start) * 1000.0))
        if budget.exhausted:
            return fallback(), True, elapsed_ms
        return value, False, elapsed_ms
