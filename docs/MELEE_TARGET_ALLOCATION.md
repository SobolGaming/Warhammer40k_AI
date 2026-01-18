# Melee Target Allocation

## Overview
When a fighting unit is engaged with more than one enemy unit, the UI now
selects melee weapons per model, then assigns each weapon bundle to targets.
Each weapon bundle can optionally split its attacks across multiple eligible
targets, and attacks resolve per target before a single consolidate step.

## Flow
1. Pile-in movement.
2. Melee weapon declaration dialog:
   - Select one main melee weapon per model (plus all [EXTRA ATTACKS]).
   - Eligible models are the union of models that can fight any target unit.
3. Weapon target allocation dialog:
   - Click a weapon row to cycle its target unit.
   - Use Split to allocate that weapon's attacks across multiple targets.
4. For each target with declarations, resolve wound allocation (if needed) and
   attacks using the core `WargearProfile.attack` pipeline.
5. Consolidate after all target groups are resolved.

## Implementation Notes
- `src/warhammer40k_ai/UI/dialogs/melee_weapon_target_allocation_dialog.py`
  handles per-weapon targeting and split allocations (with
  `src/warhammer40k_ai/UI/dialogs/melee_attack_split_dialog.py`).
- `src/warhammer40k_ai/UI/phases/phase_manager.py` sequences multi-target
  weapon selection, per-weapon allocation, and per-target resolution before
  consolidating.
- `src/warhammer40k_ai/units/wargear.py` supports `attacks_override` for
  split allocations, using `AttackCountInfo` from `preview_attack_count`.
