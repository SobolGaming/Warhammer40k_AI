# Autarch Wayleaper Abilities Completion Plan

## Status: PHASES 0-7 COMPLETE

Issue checklist for implementing the remaining Autarch Wayleaper ability support documented in `docs/factions/aeldari.md`.

## Scope

- Remaining ability: **Indomitable Strength of Will** (Autarch Wayleaper).
- Current status in `docs/factions/aeldari.md`: 4/5 supported, 1 not implemented (Indomitable Strength of Will is red).

Reference rule text (from `wahapedia_data/Datasheets_abilities.json`, datasheet id `000002759`):
> While this model is leading a unit, each time you spend a Battle Focus token to enable that unit to perform an Agile Manoeuvre, roll one D6: on a 3+, you gain 1 Battle Focus token.

## Phase 0: Source Verification

- [x] Checked official Warhammer Community sources in `docs/warhammer-community` (Core Rules, Core Rules Updates/Commentary, Balance Dataslate, MFM): no Indomitable Strength of Will rules text found; MFM only lists Autarch/Autarch Wayleaper points.
- [x] Confirmed the in-repo data:
  - `wahapedia_data/Datasheets.json` lists Autarch Wayleaper (`id` `000002759`).
  - `wahapedia_data/Datasheets_abilities.json` includes Indomitable Strength of Will text for `datasheet_id` `000002759`.
- [x] Wording confirmation: `wahapedia_data` OCR error corrected to "roll one D6" per developer confirmation.

## Phase 1: Scope and Data Mapping

- [x] Confirmed Indomitable Strength of Will is the only unsupported Autarch Wayleaper ability in `docs/factions/aeldari.md`:
  - Ability table shows **Indomitable Strength of Will** as red for Autarch Wayleaper.
  - **Path of Command** is green for Autarch/Autarch Wayleaper.
  - Unit summary row: Autarch Wayleaper 4/5 supported, 1 not implemented.
- [x] Identified Battle Focus token spend entry points: `BattleFocusManager._apply_maneuver` and `BattleFocusManager._apply_reactive_move` in `src/warhammer40k_ai/rules/battle_focus.py`.
- [x] Detection strategy chosen:
  - Add a cached Unit helper (e.g., `Unit.has_battle_focus_token_refund()`), derived from attached leader leading-only abilities.
  - Use `Unit._iter_attached_leader_leading_abilities()` with `Unit._ability_is_active()` to enforce the leading-only gate.

## Phase 2: Engine Hooks (Battle Focus Token Refund)

- [x] Add a Unit helper or `special_rules` flag to indicate Indomitable Strength of Will is active for the attached unit root.
  - Implemented `Unit.get_indomitable_strength_of_will_refund_source()` cached on the attached-unit root’s `_ability_cache`.
  - Uses `Unit._iter_attached_leader_leading_abilities()` so the “while this model is leading a unit” gate is enforced.
  - Cache invalidation on attach/detach already exists via `_invalidate_ability_cache()`; no additional attach/detach changes were required.
- [x] Wire Battle Focus token spend to trigger the refund roll:
  - Added `BattleFocusManager._maybe_refund_token_indomitable_strength_of_will()` and called it from `_apply_maneuver` and `_apply_reactive_move` after `_spend_token()` succeeds.
  - Refund roll uses `utility.dice.get_roll("D6")` and refunds 1 token on 3+.
  - Only one refund roll is performed per token spend (single helper call; first matching leader ability wins).
- [x] Add logging for transparency (event log or print) that includes:
  - Uses `utility.event_bus.append_dice()` to record the refund roll and outcome for the acting player.
- [x] Ensure refund applies to all Agile Manoeuvres (Swift, Flitting, Star Engines, Sudden Strike, Opportunity Seized, Fade Back) and only when the leader is attached.
  - Refund hook is attached to the shared token-spend paths (`_apply_maneuver` and `_apply_reactive_move`) so it applies uniformly to all manoeuvres.

## Phase 3: UI and Decision Hooks

- [x] No new player choice is introduced; confirm no new UI dialogs are required.
  - Indomitable Strength of Will’s refund is automatic on a 3+ (no “you can/may” choice), so no dialog/decision type was added.
  - No updates required in `docs/NETWORK_SAVELOAD_DESIGN.md` for dialog-to-decision mapping.
- [x] If adding user-facing log output, ensure it shows in both local and remote play logs (no UI-only state).
  - Refund roll/outcome is logged via `utility.event_bus.append_dice()` (consumed by the HUD via `get_recent_dice()` in `UI/layout/hud_layout.py`).
  - Remote parity: `NetworkGameSession` applies incoming `CommandMessage`s locally (`game.apply_command(command)`), so the same engine code paths that call `append_dice()` run on remote clients as well.
  - No UI-only state was introduced for this feature; the display is driven by engine-side logging.

## Phase 4: Serialization and Determinism

- [x] If a new `special_rules` key is added, confirm it is serializable (plain JSON types).
  - No new `special_rules` key was added for Indomitable Strength of Will; the detection is cached in `Unit._ability_cache` only.
  - Snapshot safety: `_ability_cache` is excluded from unit snapshot state via `_UNIT_STATE_EXCLUDE` in `engine/snapshot.py`, and `load_game_snapshot()` invalidates ability caches after rebuilding attachment links.
- [x] Confirm the refund roll uses the deterministic dice system and does not rely on non-seedable randomness.
  - Refund roll uses `utility.dice.get_roll("D6")`, which calls `get_dice_roll()`.
  - `get_dice_roll()` uses `get_active_game()` and records/consumes `dice_roll` events via `game.event_log` when a game context exists.
  - `Game.apply_command()` wraps command dispatch in `game_context(self)`, ensuring the active game context is set during command resolution (local + network).
- [x] No new UI dialog => no update required in `docs/NETWORK_SAVELOAD_DESIGN.md`.
  - Phase 3 confirmed no optional player choice is introduced by this ability.

## Phase 5: Tests (pytest)

Add tests to `tests/test_battle_focus.py` (preferred) or a new `tests/test_autarch_wayleaper_indomitable_strength.py`:

- [x] `test_indomitable_strength_of_will_refund_on_maneuver`:
  - Implemented with a stub unit exposing `get_indomitable_strength_of_will_refund_source()`.
  - Patch `get_roll` to return 3+.
  - Expect: tokens decrease then refund to original count.
- [x] `test_indomitable_strength_of_will_no_refund_on_low_roll`:
  - Patch `get_roll` to return 1-2.
  - Expect: tokens decrement without refund.
- [x] `test_indomitable_strength_of_will_requires_leading`:
  - Simulated “not leading” by returning an empty refund source string.
  - Expect: no refund even if the refund roll would have succeeded.
- [x] `test_indomitable_strength_of_will_applies_to_reactive_maneuver`:
  - Uses `apply_reactive_maneuver(..., MANEUVER_FADE_BACK, ...)` and patches `get_roll` with `side_effect=[distance_roll, refund_roll]`.
  - Expect: refund logic triggers on 3+.

Verification:
- Ran `uv run python -m pytest tests/test_battle_focus.py -q` -> **14 passed**.

## Phase 6: Documentation

- [x] Update `docs/factions/aeldari.md`:
  - Mark Indomitable Strength of Will as supported (green).
  - Autarch Wayleaper is now **Fully supported**.
- [x] Update support classification in `scripts/generate_ability_support_matrix.py` so the ability is marked supported:
  - Added explicit override: `(faction="AE", ability_name="Indomitable Strength of Will")` -> Supported.
  - Cleaned up accidental tab indentation so the mapping block is consistent with surrounding entries.
- [x] Regenerate docs via `python3 scripts/generate_ability_support_matrix.py` if that is the standard workflow.
  - Ran: `uv run python scripts/generate_ability_support_matrix.py`

## Phase 7: Test Runs

- [x] `python -m pytest tests/test_battle_focus.py -v` (or the new test file if created).
  - Ran: `uv run python -m pytest tests/test_battle_focus.py -v` -> **14 passed**.
- [x] `python -m pytest tests/` (rule behavior change; full suite required).
  - Ran: `uv run python -m pytest tests/` -> **952 passed**.
