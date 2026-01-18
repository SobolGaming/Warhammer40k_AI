# Reserve Limits Implementation

## Overview
The engine enforces the Chapter Approved / matched play reserve caps:
- Total reserves (Reserves + Strategic Reserves): <= 50% unit count and <= 50% battle size points
- Strategic Reserves: <= 25% battle size points

Points caps are based on `Army.points_limit` (battle size), not the army's current total points.

## Reserve groups (deployment roots)
Reserve counting is based on deployment groups:
- Attached leaders do not count separately
- Embarked units do not count separately
- The transport or bodyguard unit is the root that carries the group

Implementation helpers in `src/warhammer40k_ai/roster/army.py`:
- `_reserve_group_roots()`
- `_reserve_group_members()`
- `_reserve_group_points()`

## Army helpers
Key methods in `src/warhammer40k_ai/roster/army.py`:
- `get_reserve_limits()` returns totals and caps (`max_units`, `max_points`, `max_strategic_points`).
- `validate_reserves_decisions()` counts reserves and strategic points and forces
  `must_start_in_reserves` units into standard reserves.
- `enforce_reserves_limits()` resolves overages in this order:
  1. Force AIRCRAFT to standard reserves.
  2. If strategic points exceed the cap, downgrade to standard reserves when eligible
     (Deep Strike), otherwise deploy.
  3. If total reserves exceed caps, deploy the largest reserve groups until valid.
- `get_current_reserves_status()` supplies UI status and totals.
- `can_add_unit_to_reserves()` checks caps during interactive selection.

## UI and controller integration
- `ReservesAllocationDialog` (`src/warhammer40k_ai/UI/dialogs/reserves_allocation_dialog.py`) operates
  on reserve groups, displays caps, and blocks illegal choices:
  - Standard Reserves require Deep Strike (best-effort via `unit.has_deep_strike()`).
  - FORTIFICATIONS cannot be placed into Strategic Reserves.
- `HumanDeploymentDecisionMaker.declare_reserves()` uses the same Army helpers for console fallback.

## Application to game state
- `DeploymentManager.set_reserves_status()` applies decisions to the root unit and propagates the
  status to attached leaders and embarked passengers.
- Units starting in reserves are tagged with `_started_in_reserves` for round-3 destruction logic.

## Files
- `src/warhammer40k_ai/roster/army.py`
- `src/warhammer40k_ai/UI/dialogs/reserves_allocation_dialog.py`
- `src/warhammer40k_ai/engine/deployment.py`
