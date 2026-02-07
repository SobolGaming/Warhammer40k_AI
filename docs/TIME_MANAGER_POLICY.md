# Time Manager Policy

The engine assigns a per-decision `time_budget_ms` in decision context.

Defaults:
- Decision caps:
  - `MOVE_UNIT`: 220ms
  - `SELECT_TARGETS`: 140ms
  - `PLAY_STRATAGEM`: 60ms
  - `DECLARE_CHARGE`: 120ms
  - fallback default: 150ms
- Compute tier multipliers:
  - `P0`: 1.8
  - `P1`: 1.0
  - `P2`: 0.5

Budget derivation:
- `time_budget_ms = round(cap(decision_type) * multiplier(compute_tier))`

Timeout behavior:
- Time-constrained helpers may return fallback/best-so-far candidates when wall-clock exceeds budget.
- Decision telemetry records both `time_budget_ms` and `wall_clock_ms` for each decision.
