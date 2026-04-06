# Pile-In + Consolidate Movement Implementation

## Overview
Pile-in and consolidate movement are validated in `src/warhammer40k_ai/utility/calcs.py`
using `MovementType.PILE_IN` and `MovementType.CONSOLIDATE`. The UI surfaces the same
rules through the per-model movement dialog and range visualization. Fight-phase
activation now queues authoritative `MOVE_UNIT` decisions for both pile-in and
consolidate, so local UI, remote UI, and headless controllers all use the same
decision type and move validation path.

Cross-links:
- `get_validation_rules(...)`: `src/warhammer40k_ai/utility/calcs.py`
- Final-position validation (pile-in/consolidate): `src/warhammer40k_ai/utility/calcs.py`
- Fight-phase distance overrides: `Unit.get_fight_phase_move_distance_override(...)` in
  `src/warhammer40k_ai/units/unit.py`
- Fight move planning/validation helpers: `src/warhammer40k_ai/engine/fight_move.py`
- Fight-phase `MOVE_UNIT` sequencing facade: `src/warhammer40k_ai/engine/fight_phase_manager.py`
- Fight ordering / engagement / resolution helpers: `src/warhammer40k_ai/engine/fight_order.py`,
  `src/warhammer40k_ai/engine/fight_engagement.py`, `src/warhammer40k_ai/engine/fight_resolution.py`
- Edition-aware fight timing profile: `src/warhammer40k_ai/engine/combat_timing.py`

## Pile-In rules enforced
- Models already in base-to-base contact cannot pile in.
- Each model must end closer to the closest enemy model (or closest enemy unit when the
  `closest_enemy_unit` rule flag is active).
- If base contact is achievable within the pile-in distance, the move must end in
  base-to-base contact.
- Pile-in distance is capped by `PILE_IN_DISTANCE` (3.0") unless overridden.

## Consolidate rules enforced
- Models already in base-to-base contact cannot consolidate.
- Each model must end closer to the closest enemy model (or closest enemy unit when the
  `closest_enemy_unit` rule flag is active).
- If it is possible to end within Engagement Range of an enemy unit, the model must do so.
- If ending in Engagement Range is not possible, the model may instead end closer to the
  closest objective marker and within that marker’s control radius (objective fallback).
- If base contact is achievable within the consolidate distance, the move must end in
  base-to-base contact.
- Consolidate distance is capped by `CONSOLIDATE_DISTANCE` (3.0") unless overridden.

## Performance optimization
Pile-in/consolidate validation only considers enemies within:
`ENGAGEMENT_RANGE_HORIZONTAL + move_distance` (pile-in or consolidate distance).

This reduces the candidate set while keeping validation correct for pile-in legality.

## Timing profile hook
- Fight-stage starting-player selection and enabled move steps are read through
  `engine/combat_timing.py`.
- The current runtime keeps the standard non-active-player-first flow with both
  pile-in and consolidate enabled, but that policy is now centralized behind the
  combat timing profile rather than buried directly in `fight_phase_manager.py`.

## UI behavior
- `IndividualModelMovementDialog` lists all models and disables those already in base
  contact with a reason tooltip.
- Pile-in/consolidate share the same per-model movement dialog and range visualization.
- Remote/non-authoritative clients open the same movement dialog from the queued
  `MOVE_UNIT` request when `context.phase_name="FIGHT_PHASE"` and
  `movement_type` is `pile_in` or `consolidate`.

## Headless behavior
- Headless fight activations resolve pile-in/consolidate through `MOVE_UNIT`
  candidate generation rather than legacy auto-move stubs.
- The engine revalidates submitted pile-in/consolidate `model_positions`
  against pathing and coherency before applying them.

## Constants
Defined in `src/warhammer40k_ai/utility/constants.py`:
- `PILE_IN_DISTANCE`
- `CONSOLIDATE_DISTANCE`
- `BASE_CONTACT_EPSILON`

## Supported overrides and special rules
These are applied via `Unit.get_fight_phase_move_distance_override(...)` or validation flags
in `utility.calcs.get_validation_rules(...)`.
- **Distance overrides (pile-in/consolidate):**
  - `Battle Focus: Sudden Strike` (6" pile-in/consolidate) via `battle_focus_sudden_strike_expires_phase`.
  - `Blessings of Khorne: Rage-Fuelled Invigoration` (6" pile-in/consolidate) while active.
  - Consolidate stratagems parsed in `rules/stratagems.py` can set
    `stratagem_consolidate_distance_override`.
  - Datasheet/enhancement abilities with text like "Each time this model's unit Consolidates, it can move up to 6\" instead of up to 3\"" set
    `bearer_unit_consolidate_distance_override` (consolidate only).
  - Leading abilities with text like "While this model is leading a unit, each time that unit Piles In or Consolidates, each model in that unit can move up to 6\" instead of up to 3\""
    set both `bearer_unit_pile_in_distance_override` and `bearer_unit_consolidate_distance_override`.
- **Consolidate must end in Engagement Range:**
  - Some consolidate stratagems set `stratagem_consolidate_requires_engagement`.
- **Closest enemy unit rule:**
  - Templar Vows can switch the “closest enemy model” check to “closest enemy unit.”
- **Aircraft exclusions:**
  - Non-flying units exclude AIRCRAFT when determining closest enemy for pile-in/consolidate.

## Future-supported abilities (tracked but not yet generalized)
- Additional datasheet abilities or stratagems that alter consolidate destination rules
  (e.g., “consolidate towards objectives” variants beyond the current objective fallback)
  should be wired into validation flags in `get_validation_rules(...)`.

## Tests
Relevant tests include:
- `tests/test_fight_phase_pile_in_consolidate_rules.py`
- `tests/test_pile_in_simple.py`
- `tests/test_pile_in_visualization.py`
- `tests/test_collision_detection.py`
- `tests/test_aircraft_rules.py`
