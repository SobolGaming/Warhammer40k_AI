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

## Follow-up Phase 1 (option 1)
- Targeted hardening pass in:
  - `src/warhammer40k_ai/rules/stratagems.py`
  - `src/warhammer40k_ai/engine/game.py`

### `stratagems.py`
- Replaced `print(...)` fallback with structured logging in `Stratagem.use(...)`.
- Removed no-op `try/except Exception: raise` wrappers in core helper paths:
  - consolidate parser integer parsing
  - refresh/cache rebuild
  - defensive spec scanning in event subscription setup
  - reaction dequeuing
  - attacker key resolution
  - defensive-effect append path
- Refactored consolidate engagement feasibility checks to use explicit callable checks plus typed numeric parsing (`TypeError`/`ValueError`) instead of broad exception handling.

### `game.py`
- Tightened startup exception handling:
  - Headless agent import now only suppresses `ImportError`.
  - `unit_destroyed` subscription is no longer wrapped in broad swallow logic.
- Refactored `_on_unit_destroyed_monarch_of_the_hunt(...)` to eliminate broad exception swallowing:
  - explicit player/army/unit resolver helpers
  - explicit callable checks for request builder hooks
  - deterministic quarry repick evaluation without hidden failures
- Replaced broad exception swallowing in:
  - battle-shock resolution handlers (`shadow_form`, `harbingers`) with narrower handling/callable checks
  - Maggot Maws event logging path (no silent drop)
  - command-phase optional prompt paths (direct imports/callable publish checks)

### Snapshot impact
- `stratagems.py` scan count moved from `excepts=1429, prints=583` to `excepts=1409, prints=582`.
- `game.py` scan count moved from `excepts=718, prints=98` to `excepts=692, prints=98`.
