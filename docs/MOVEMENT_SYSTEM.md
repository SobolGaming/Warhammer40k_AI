## Movement System Overview

This document describes how all movement types are implemented in the engine today.
It focuses on pathing, movement allowances, coherency, pivoting, and the rule-specific
movement validations used by Normal moves, Advances, Fall Back moves, Charges, and
fight-phase moves.

Related docs:
- [Charge roll modifiers](docs/CHARGE_ROLL_MODIFIERS.md): charge roll math and modifiers.
- [Pile-in and consolidate implementation](docs/PILE_IN_AND_CONSOLIDATE_IMPLEMENTATION.md): fight-phase move intent and UI flow.
- [Ruins terrain system](docs/RUINS_TERRAIN_SYSTEM.md): ruins geometry and floor rules.
- [Model geometry overrides](docs/MODEL_GEOMETRY_OVERRIDES.md): compound footprints and z-offset geometry inputs used by distance/pathing.

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

The authoritative movement planner API now lives in `src/warhammer40k_ai/pathing/api.py`:
`plan_model_path`, `preview_model_path`, `validate_final_pose`, and
`compute_swept_interactions`.
Movement capability extraction lives in `src/warhammer40k_ai/pathing/rules_profile.py`
as `MovementProfile` (defined in `src/warhammer40k_ai/pathing/types.py`), while
unit-level action orchestration is in `src/warhammer40k_ai/units/unit.py`.

### Pathing and movement allowance

Pathfinding is layered CDT + corridor-aware SE(2) refinement. Important building blocks:
- `pathing/api.py`:
  `plan_model_path()` / `preview_model_path()` for routing,
  `validate_final_pose()` for endpoint legality,
  `compute_swept_interactions()` for swept-footprint interactions.
- `movement_segment_cost()` and `measure_path_distance()` for rules-aware distance.
- `measure_direct_distance()` for straight-line checks prior to pathfinding.
- `get_terrain_blocking_polygons()` and `is_terrain_impassable()` for collision gating.
- `build_movement_profile()` for deterministic movement capability extraction
  (climb thresholds, vertical-ignore behavior, breaches, engagement/fall-back interaction flags).
- `pathing/surfaces.py` and `pathing/world_snapshot.py` for deterministic layered support
  extraction (GROUND + RUINS floors + explicit elevated support tops) and immutable
  per-query world snapshots.
- `pathing/dynamic_overlay.py` for deterministic live model blocker overlays keyed by
  army identity rather than faction string.
- World/surface revisions are fingerprinted from normalized geometry encodings
  (not only bounds/area summaries), so cache keys can safely distinguish equal-summary
  but different polygons.
- `pathing/cdt_mesh.py`, `pathing/surface_graph.py`, `pathing/corridor.py`, and
  `pathing/cache.py` now provide the circular-base Phase C planner substrate:
  clearance-eroded free-space triangulation, portal/connector A*, funnel corridor
  recovery, and static mesh cache keys based on terrain/support/profile revisions
  plus exact circular clearance keys.
- Cross-surface connectors are now represented as deterministic sampled anchors over
  overlap geometry (not a single representative point), so blocked/awkward anchors
  can be bypassed by another legal overlap anchor.
- `pathing/se2_refine.py` now provides Phase D local exact corridor refinement for
  non-circular/compound footprints and narrow portal corridors, validating sampled
  pose transitions with exact `get_base_shape_at(...)` geometry and support checks.
  The SE(2) search is endpoint-anchored (exact start pose and exact segment end
  pose), and its one-time pivot cost uses existing unit/base pivot semantics.
- `pathing/sweep.py` provides shared swept-footprint geometry used by
  `compute_swept_interactions()` to report moved-over enemy model ids from exact
  footprint sweeps instead of centerline-only checks.
- Segment legality uses a swept-base check between waypoints so thin walls cannot be
  tunneled through by center-point interpolation artifacts.

Friendly/enemy blocker classification in movement collision trees is based on parent-army
identity (with faction fallback only when army identity is unavailable), preventing mirror-match
misclassification when both sides share the same faction string.

Layered support semantics now used by pathing infrastructure:
- Ground-layer transit ignores low terrain whose top/wall height is
  `<= MovementProfile.free_climb_height_inches`.
- Support placement on elevated/top surfaces is footprint-exact:
  circular bases use support-polygon erosion by radius, while non-circular/compound
  bases use full `get_base_shape_at(...)` containment checks.

Movement allowance interacts with pathing in two steps:
1. A direct-distance check ensures the destination is in range.
2. The path distance is computed; if it exceeds the allowance, the model moves as far
   along the path as possible (Normal and Advance moves), or the move is rejected
   (charges must fit the distance).

### Pivoting and rotation cost

Pivoting is modeled as a movement cost for certain bases and large models.
The pivot cost is applied inside pathfinding for all movement types, including fight-phase moves.

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
            'apply_pivot_cost': True,
            ...
        })
    elif movement_type == MovementType.CONSOLIDATE:
        ...
        base_rules.update({
            ...
            'apply_pivot_cost': True,
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

The action handler also gates movement due to transport disembark restrictions,
including immediate disembarks after a reserves transport is set up, and publishes
movement-start/finish events for reaction windows.

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

#### Move-over mortal wound triggers

Some abilities trigger when a model ends a Normal or Advance move and it moved over an
enemy unit. The engine now detects “moved over” with swept-footprint geometry:
- the model footprint is swept across sampled path poses (including rotation-sensitive bases),
- enemy candidates are selected when their base geometry intersects that swept area,
- optional vertical-band gating is then applied so vertical-only flyovers (e.g. different RUINS
  floors) are not counted when rules require vertical overlap.
- for API callers, this gate is controlled by `PathQuery.sweep_require_vertical_overlap`.

The same swept-overlap detection is used for Fall Back / Desperate Escape checks and for
move-over triggered abilities. These triggers are evaluated only for FLY units where required
by the ability text.

When eligible, the UI prompts to select one of the moved-over enemy units (with a Skip option).
Currently supported pattern:
- “Each time this model ends a Normal or Advance move … roll X D6; for each Y+, that enemy
  unit suffers Z mortal wounds.” (fixed dice count and fixed mortal-per-success only).

#### Reactive enemy-move D6 triggers

Some abilities allow a reactive Normal move when an enemy unit ends a Normal, Advance, or
Fall Back move within range (e.g., Trail Finding / Loping Speed). The engine:
- Parses matching ability text via `_ENEMY_MOVE_REACTIVE_D6_RE`.
- Listens for `unit_move_ended` (move/advance/fall_back) and checks 3D range + engagement.
- Prompts the controlling player and rolls D6 for max distance, enforcing once per turn.

### Aircraft movement

AIRCRAFT movement uses a dedicated path (see `Unit._aircraft_normal_move()`):
- AIRCRAFT can only make Normal moves (no Advance/Fall Back/Remain Stationary).
- Each Normal move is straight forward with a minimum of 20" and no upper limit.
- After the straight move, the model can pivot up to 90° without costing distance.
- If the minimum move is impossible or the move crosses the battlefield edge, the model is placed into Strategic Reserves and returns next turn.

### Charge movement

Charge movement is handled by `Unit.charge_move()` and uses charge-aware pathfinding.
Key differences from Normal moves:
- Requires one or more declared target units (multi-target charges are supported).
- The unit must end in Engagement Range of every declared target unit.
- The unit cannot end within Engagement Range of any non-target enemy units.
- Uses `plan_model_path(PathQuery(..., movement_type=MovementType.CHARGE, ...))`
  with charge-specific validation rules.

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
- Pivot costs apply normally; if a model pivots, the pivot value reduces its remaining distance.

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
- `move_over_low_terrain_height_*` raises the freely climbable threshold for specific
  move types (e.g., Normal/Advance/Fall Back) so terrain <= X" is treated as "move over".
- `bearer_unit_phase_move_terrain_only_types` enables phase-gated terrain pass-through
  (for example, Normal/Advance/Fall Back/Charge move-through-terrain abilities).
- `bearer_unit_phase_move_models_only_*` enables model pass-through (optionally with
  TITANIC blocking) without automatically granting full terrain pass-through.
- `has_flip_belt` ignores vertical distance for allowed move types.
- `has_super_heavy_walker` extends the freely climbable height.
- `move_over_friendly_monster_vehicle_*` permits moving through friendly MONSTER/VEHICLE.

These are primarily interpreted in `utility/calcs.py` and in `Unit` helpers.
