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
- Valid compute tiers are `P0`, `P1`, and `P2`. Optional orchestration context
  normalizes invalid, empty, or unknown values to `P1` before time-budget
  decoration.

Budget derivation:
- `time_budget_ms = round(cap(decision_type) * multiplier(compute_tier))`
- minimum budget is clamped to `1ms`
- `MOVE_UNIT` examples:
  - `P0`: `round(220 * 1.8) = 396ms`
  - `P1`: `round(220 * 1.0) = 220ms`
  - `P2`: `round(220 * 0.5) = 110ms`

Timeout behavior:
- `TimeManager.run_with_time_budget(...)` measures wall clock around the full solver action call.
- If elapsed wall clock is `> budget_ms`, the time manager returns the provided fallback value and marks `fallback_used=True`.
- This is a post-action enforcement contract (soft cap): the action is not interrupted mid-call.
- Budget-aware solvers are therefore expected to cooperate with the deadline they receive and avoid unbounded inner searches.

## Movement Solver Fallback Contract (PR-AI-011)

For `DECISION_MOVE_UNIT`, `Game.request_decision(...)` decorates context via `TimeManager` and calls
`generate_move_unit_candidates(...)`.

When `time_budget_ms > 0` and a `TimeManager` is present:
- solver action executes through `run_with_time_budget(...)`.
- movement candidate generation passes the soft deadline into internal helpers so charge/fight move planning can prefer bounded heuristic search before expensive routed/pathing fallback.
- charge MOVE_UNIT candidate generation uses a bounded endpoint heuristic while under a deadline. The heuristic translates the unit from the actual closest charging model to the endpoint so multi-model unit charges are not anchored on arbitrary model ordering. If that heuristic cannot produce a legal charge candidate, it returns the deterministic skip/fallback candidates instead of entering exact routed charge pathing, because the routed path planner can spend unbounded time inside geometry calls that cannot be interrupted mid-call.
- on over-budget elapsed runtime:
  - solver output is discarded.
  - fallback candidates are rebuilt deterministically from `request.candidates` (already canonicalized/sorted by action id).
  - fallback candidate metadata sets `fallback_mode=true`.
  - fallback mask reuses `request.mask`; if lengths diverge, mask is reset to all `True`.
- on in-budget elapsed runtime:
  - solver candidates are returned unchanged.
  - `fallback_mode=false`.

When no time manager is present or budget is non-positive:
- movement solver runs directly without budget fallback wrapping.

Telemetry behavior:
- movement candidates are annotated with `solver_ms` and final `fallback_mode` at request-time normalization.
- Decision telemetry records both `time_budget_ms` and `wall_clock_ms` for each decision.
