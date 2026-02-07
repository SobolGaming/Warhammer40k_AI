# Codebase Hardening (2026-02-07)

## Scope
- Remove error-hiding patterns in selected non-`Unit` core modules.
- Replace ad-hoc prints with structured logging in `Player` CP/secondary flows.
- Fix faction-rule manager wiring bug for Genestealer Cults.

## Changes
- `src/warhammer40k_ai/engine/command_dispatcher.py`
  - Removed broad `except Exception` masking in decision validation.
  - Replaced direct `print(...)` diagnostics with `logger.error(...)`.
  - Imported dice-roll decision constants directly to avoid silent import fallback.
- `src/warhammer40k_ai/UI/decision_controller.py`
  - Removed broad exception swallowing when resolving player control.
  - Switched to explicit callable checks for `_resolve_player_by_id` and `has_control`.
- `src/warhammer40k_ai/units/attached_unit.py`
  - Removed broad exception swallowing during member/model flattening.
  - Switched to explicit attribute/callable checks for deterministic failures.
- `src/warhammer40k_ai/roster/player.py`
  - Removed broad exception swallowing in multiple CP-cost/ability helper paths.
  - Replaced informational `print(...)` calls with module logger calls.
  - Added shared helper `_target_unit_parent_army(...)` to reduce duplicated parent-army resolution logic.
- `src/warhammer40k_ai/roster/army.py`
  - Fixed Genestealer Cults manager gate from `fid == "GSC"` to `fid == "GC"` so `DeathstrikeManager` is correctly configured.

## Tests
- Added `tests/test_army_rule_manager_configuration.py`:
  - Verifies `Army(faction_id="GC")` configures `DeathstrikeManager`.

