## Movement System Overview

This document describes how all movement types are implemented in the engine today.
It focuses on pathing, movement allowances, coherency, pivoting, and the rule-specific
movement validations used by Normal moves, Advances, Fall Back moves, Charges, and
fight-phase moves.

Related docs:
- [Charge roll modifiers](docs/CHARGE_ROLL_MODIFIERS.md): charge roll math and modifiers.
- [Pile-in and consolidate implementation](docs/PILE_IN_AND_CONSOLIDATE_IMPLEMENTATION.md): fight-phase move intent and UI flow.
- [Ruins terrain system](docs/RUINS_TERRAIN_SYSTEM.md): ruins geometry and floor rules.

Potential future split-outs (if this grows):
- Charge movement
- Pile-in and consolidate movement
- Terrain movement
- Special movement rules (ability-specific)
- Fly movement rules

### Core concepts

Movement is model-level pathfinding with unit-level validation:
- Each model in a unit gets its own path.
- Coherency is validated after all model moves are resolved.
- If coherency would be broken, the move is rejected and rolled back.

The primary movement utilities live in `src/warhammer40k_ai/utility/calcs.py`, while
the unit-level action orchestration is in `src/warhammer40k_ai/units/unit.py`.

```9442:9536:src/warhammer40k_ai/units/unit.py
        from ..utility.calcs import get_individual_model_movement_path, process_unit_movement_with_coherency_check
        ...
        # NEW: Validate unit coherency after all models have moved
        is_coherent, non_coherent_models = process_unit_movement_with_coherency_check(self, model_movements)
        
        if not is_coherent:
            print(f"{self.name} move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
            # ROLLBACK: Restore original positions (movement ending out of coherency is not allowed)
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
```

### Pathing and movement allowance

Pathfinding is A*-based and terrain-aware. Important building blocks:
- `get_individual_model_movement_path()` and `unified_pathfinding()` for model-level routing.
- `movement_segment_cost()` and `measure_path_distance()` for rules-aware distance.
- `measure_direct_distance()` for straight-line checks prior to pathfinding.
- `get_terrain_blocking_polygons()` and `is_terrain_impassable()` for collision gating.

Movement allowance interacts with pathing in two steps:
1. A direct-distance check ensures the destination is in range.
2. The path distance is computed; if it exceeds the allowance, the model moves as far
   along the path as possible (Normal and Advance moves), or the move is rejected
   (charges must fit the distance).

### Pivoting and rotation cost

Pivoting is modeled as a movement cost for certain bases and large models.
The pivot cost is applied inside pathfinding and can be disabled for fight-phase moves.

```1174:1265:src/warhammer40k_ai/utility/calcs.py
def get_validation_rules(movement_type: MovementType, target_unit: 'Unit' = None, *, moving_unit: 'Unit' = None) -> dict:
    ...
    base_rules = {
        ...
        'apply_pivot_cost': True,           # Always apply pivot costs
        ...
    }
    ...
    elif movement_type == MovementType.PILE_IN:
        ...
        base_rules.update({
            ...
            # Fight phase moves should not pay pivot cost; this was causing valid 3" moves to be rejected.
            'apply_pivot_cost': False,
            ...
        })
    elif movement_type == MovementType.CONSOLIDATE:
        ...
        base_rules.update({
            ...
            # Fight phase moves should not pay pivot cost; this was causing valid 3" moves to be rejected.
            'apply_pivot_cost': False,
            ...
        })
```

Pivot cost itself is defined in `get_pivot_cost()` and `Map.calculate_pivot_cost()`.

### Movement actions and states

Movement actions are `MovementAction` values applied through `Unit._execute_action()`:
- `REMAIN_STATIONARY`
- `MOVE` (Normal move)
- `ADVANCE`
- `FALL_BACK`

The action handler also gates movement due to transport disembark restrictions and
publishes movement-start/finish events for reaction windows.

```6614:6726:src/warhammer40k_ai/units/unit.py
    def get_available_move_actions(self, state: int) -> List[int]:
        """Get the list of available actions based on the current state."""
        ...
        # AIRCRAFT: only Normal moves allowed (no Advance/Fall Back/Remain Stationary).
        if bool(getattr(self, "is_aircraft", False)):
            return [MovementAction.MOVE.value]
        ...
    def _execute_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map', advance_roll: int = None) -> bool:
        """Execute a movement action for the unit."""
        ...
        if action == MovementAction.REMAIN_STATIONARY.value:
            print(f"{self.name} remains stationary")
            success = self.remain_stationary()
        elif action == MovementAction.MOVE.value:
            print(f"{self.name} moves to {destination}")
            success = self.move(destination, game_map)
        elif action == MovementAction.ADVANCE.value:
            print(f"{self.name} advances to {destination}")
            success = self.advance(destination, game_map)
        elif action == MovementAction.FALL_BACK.value:
            print(f"{self.name} falls back")
            success = self.fall_back(destination, [], game_map)
        ...
```

#### Remain Stationary

`Unit.remain_stationary()` marks the unit as having remained stationary and blocks the
action for AIRCRAFT. This is a pure state update; no positions change.

#### Normal Move

`Unit.move()` drives standard movement:
- Ensures the unit can move (reserves constraints, AIRCRAFT special path).
- Calculates model destinations using `calculate_model_positions()`.
- Uses model-level pathfinding per model.
- Validates coherency and collisions post-move; rolls back if invalid.

#### Advance

`Unit.advance()` is a Normal move with an added advance roll. The advance roll:
- Is stored in `round_state.advance_roll`.
- Can be fixed by some rules (e.g., special rules such as Pain tokens).
- Can be modified by abilities and auras.
- Is re-rollable via UI prompts when eligible.

Advance still uses the same pathfinding and coherency validation as Normal move.

#### Fall Back

Fall Back is executed by `Unit.fall_back()` (called via `_execute_action`) and uses
MovementType rules that:
- allow moving through enemy models, and
- prevent ending in engagement range,
- optionally trigger Desperate Escape checks.

These constraints are encoded in `get_validation_rules()`:

```1296:1312:src/warhammer40k_ai/utility/calcs.py
    elif movement_type == MovementType.FALL_BACK:
        base_rules.update({
            'can_move_through_enemy_models': True,  # Can move through enemy models
            'cannot_end_in_engagement_range': True,  # Cannot end within engagement range
            'check_desperate_escape': True,  # Check if Desperate Escape tests are needed
        })
    elif movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
        base_rules.update({
            'cannot_move_within_engagement_range': True,  # Cannot move within 1" of enemies
        })
```

### Charge movement

Charge movement is handled by `Unit.charge_move()` and uses charge-aware pathfinding.
Key differences from Normal moves:
- Requires a target unit.
- Allows ending in engagement range.
- Uses `get_charge_movement_path()` and charge-specific validation rules.

Charge roll behavior and modifiers are documented in [Charge roll modifiers](docs/CHARGE_ROLL_MODIFIERS.md).

```9595:9715:src/warhammer40k_ai/units/unit.py
    def charge_move(self, destination: Tuple[float, float, float], game_map: 'Map', target_unit: 'Unit' = None) -> bool:
        """Special movement for charge actions that allows moving into engagement range.
        
        Unlike normal movement, charge movement:
        1. Allows models to move into engagement range of enemy units
        2. Uses relaxed collision detection for final positioning
        3. Prioritizes achieving engagement range over perfect formations
        """
        ...
        max_charge_distance = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.CHARGE,
            game_map,
        )
        ...
```

Coherency is still required after charge moves and validated separately.

### Fight-phase movement (Pile-in and Consolidate)

Pile-in and consolidate moves are expected to be UI-controlled and use
the same pathfinding/validation system with different rule constraints:
- Must end closer to enemies (pile-in) or closer to enemies/objectives (consolidate).
- Max move distances are governed by `PILE_IN_DISTANCE` and `CONSOLIDATE_DISTANCE`,
  with possible overrides from rules.
- Pivot costs are disabled for these moves to avoid rejecting valid 3" moves.

See [Pile-in and consolidate implementation](docs/PILE_IN_AND_CONSOLIDATE_IMPLEMENTATION.md) for the workflow and UI details.

### Terrain movement

Terrain is evaluated in `utility/calcs.py`:
- `get_terrain_blocking_polygons()` defines impassable shapes.
- `is_terrain_impassable()` decides what blocks movement for a given unit.
- `can_traverse_freely()` decides whether vertical cost is ignored.

RUINS have special logic for wall traversal and floor selection. See
[Ruins terrain system](docs/RUINS_TERRAIN_SYSTEM.md) for the terrain system details.

### Fly rules and vertical distance

Fly-related behavior lives in `utility/calcs.py`:
- FLY is allowed for MovementTypes move/advance/fall back/charge.
- Flying units ignore some vertical distances in `movement_segment_cost()`.
- FLY can alter terrain traversal and engagement considerations.

This logic is exposed by helper functions such as `_unit_is_fly_move()` and
`_movement_type_allows_fly_over()`, and through `get_validation_rules()`.

### Coherency validation and movement allowance

Coherency is validated after model positions are chosen:
- Normal/Advance moves use `process_unit_movement_with_coherency_check()`.
- Charge moves use `validate_unit_coherency_after_movement()`.

If a move would exceed movement allowance, the model path is truncated. Coherency
checks are still performed on the final positions. If coherency fails, the move is
rejected even if each individual model stayed within its movement allowance.

### Special movement rules (ability-specific)

Several abilities encode movement exceptions as `special_rules` flags and are folded
into validation or distance logic:
- `move_over_low_terrain_height_*` modifies the climbable threshold.
- `has_flip_belt` ignores vertical distance for allowed move types.
- `has_super_heavy_walker` extends the freely climbable height.
- `move_over_friendly_monster_vehicle_*` permits moving through friendly MONSTER/VEHICLE.

These are primarily interpreted in `utility/calcs.py` and in `Unit` helpers.
