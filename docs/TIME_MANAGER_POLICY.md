# Time Manager Policy

The engine assigns per-decision `time_budget_ms` and `work_budget_units` in
decision context. Wall-clock time remains telemetry; deterministic work units
control gameplay-affecting fallback decisions.

Defaults:
- Decision caps:
  - `MOVE_UNIT`: 220ms
  - `SELECT_TARGETS`: 140ms
  - `PLAY_STRATAGEM`: 60ms
  - `DECLARE_CHARGE`: 120ms
  - fallback default: 150ms
- Work-unit caps:
  - `MOVE_UNIT`: 900
  - `SELECT_TARGETS`: 600
  - `PLAY_STRATAGEM`: 250
  - `DECLARE_CHARGE`: 500
  - `DECLARE_SHOTS`: 1200
  - `SELECT_UNIT`: 500
  - `RESERVES_ARRIVAL`: 850
  - fallback default: 600
- Compute tier multipliers:
  - `P0`: 1.8
  - `P1`: 1.0
  - `P2`: 0.5
- Valid compute tiers are `P0`, `P1`, and `P2`. Optional orchestration context
  normalizes invalid, empty, or unknown values to `P1` before time-budget
  decoration.

Budget derivation:
- `time_budget_ms = round(cap(decision_type) * multiplier(compute_tier))`
- `work_budget_units = round(work_cap(decision_type) * multiplier(compute_tier))`
- minimum time and work budgets are clamped to `1`
- `MOVE_UNIT` examples:
  - `P0`: `round(220 * 1.8) = 396ms`
  - `P1`: `round(220 * 1.0) = 220ms`
  - `P2`: `round(220 * 0.5) = 110ms`
  - `P0` work units: `round(900 * 1.8) = 1620`
  - `P1` work units: `round(900 * 1.0) = 900`
  - `P2` work units: `round(900 * 0.5) = 450`

Budget behavior:
- `TimeManager.run_with_time_budget(...)` measures wall clock around the full solver action call for telemetry.
- The solver receives a `WorkBudget` and consumes units for deterministic search work.
- If `WorkBudget.exhausted` becomes true, the time manager returns the provided fallback value and marks `fallback_used=True`.
- Elapsed wall clock never triggers gameplay fallback. Profiling overhead can increase `wall_clock_ms` and sidecar profile timings, but it must not change candidate generation, fallback selection, or match trajectory.
- Budget-aware solvers are expected to cooperate with the work budget and avoid unbounded inner searches.

## Movement Solver Fallback Contract (PR-AI-011)

For `DECISION_MOVE_UNIT`, `Game.request_decision(...)` decorates context via `TimeManager` and calls
`generate_move_unit_candidates(...)`.

When `time_budget_ms > 0` and a `TimeManager` is present:
- solver action executes through `run_with_time_budget(...)`.
- movement candidate generation passes the work budget into internal helpers so charge/fight move planning can prefer bounded heuristic search before expensive routed/pathing fallback.
- charge MOVE_UNIT candidate generation uses a bounded endpoint heuristic while a work budget is present. The heuristic translates the unit from the actual closest charging model to the endpoint so multi-model unit charges are not anchored on arbitrary model ordering. If that heuristic cannot produce a legal charge candidate, it returns the deterministic skip/fallback candidates instead of entering exact routed charge pathing, because the routed path planner can spend unbounded time inside geometry calls that cannot be interrupted mid-call.
- on exhausted work budget:
  - solver output is discarded.
  - fallback candidates are rebuilt deterministically from `request.candidates` (already canonicalized/sorted by action id).
  - fallback candidate metadata sets `fallback_mode=true`.
  - fallback mask reuses `request.mask`; if lengths diverge, mask is reset to all `True`.
- on available work budget:
  - solver candidates are returned unchanged.
  - `fallback_mode=false`.

When no time manager is present or budget is non-positive:
- movement solver runs directly without budget fallback wrapping.

Telemetry behavior:
- movement candidates are annotated with final deterministic `fallback_mode` at request-time normalization.
- wall-clock solver timings are not written into candidate metadata; they are excluded from canonical deterministic signatures and should remain in record-level telemetry or profile/report artifacts.
- Decision telemetry records both `time_budget_ms` and `wall_clock_ms` for each decision.
- Decision context records `budget_mode=work_units`, `work_budget_units`, `work_units_used`, `work_budget_exhausted`, and `work_budget_exhausted_reason` for budgeted solvers.
- Headless reserves-arrival brute-force search uses deterministic work units derived from the existing `max_reserves_arrival_seconds` configuration; the legacy seconds value no longer acts as a gameplay-changing wall-clock timeout.
