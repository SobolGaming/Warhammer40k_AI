You are working in: /Users/andrzej.gorski/Documents/Projects/Warhammer40k_AI

Implement a full movement-pathing refactor with this exact target:
- Layered CDT global planner (2.5D support surfaces)
- Local exact SE(2) corridor refiner for tight-gap orientation-sensitive movement
- Swept-footprint moved-over checks
- Full removal of legacy pathfinding code paths from utility/calcs.py
- One authoritative planner API used by preview + execution + charge + pile-in/consolidate + fall back

Hard constraints:
1. Follow AGENTS.md strictly.
2. No broad exception catches (no `except Exception`, no bare `except`).
3. No legacy pathing wrappers left in `utility/calcs.py`.
4. Use army/team identity (parent army), not faction string, for friendly/enemy classification and caching.
5. Keep deterministic ordering for connectors, graph nodes, and candidate outputs.
6. Do not add voxel/full-3D grid planner.

Implementation phases (execute in order):

PHASE A — Rules extraction and freeze
- Create `src/warhammer40k_ai/pathing/rules_profile.py`.
- Create `MovementProfile` in `src/warhammer40k_ai/pathing/types.py`.
- Move movement-rule extraction logic out of `utility/calcs.py` into `rules_profile.py`:
  - free_climb_height_inches (2" default, 4" when applicable)
  - can_ignore_vertical_distance
  - can_breach_ruins_walls
  - can_end_on_upper_surfaces
  - can_move_through_enemy_models
  - can_move_through_friendly_models
  - pivot_cost_mode (preserve existing semantics)
  - engagement_buffer_rules
  - terrain_transition_rules
  - fall_back_interaction_rules
- Fix blocker classification bug now: parent-army identity drives friend/enemy, including cache keys.

PHASE B — Layered support surfaces
- Add:
  - `src/warhammer40k_ai/pathing/world_snapshot.py`
  - `src/warhammer40k_ai/pathing/surfaces.py`
  - `src/warhammer40k_ai/pathing/dynamic_overlay.py`
- Represent layered surfaces:
  - GROUND
  - RUINS floors/catwalks/elevated supports
- Transit rule:
  - Terrain <= free_climb_height_inches is ignored for transit on ground layer.
- Placement/support legality:
  - Final/top-surface placement requires full footprint support.
  - Circular bases: support polygon erosion by radius.
  - Elliptical/hull/compound: exact footprint coverage checks using existing base-shape geometry (`get_base_shape_at`).
- Snapshot must be immutable and deterministic.

PHASE C — CDT global planner for circular/common case
- Add:
  - `src/warhammer40k_ai/pathing/cdt_mesh.py`
  - `src/warhammer40k_ai/pathing/surface_graph.py`
  - `src/warhammer40k_ai/pathing/corridor.py`
  - `src/warhammer40k_ai/pathing/cache.py`
- Build free-space per surface:
  - walkable/support polygon
  - minus static cutouts
  - minus dynamic overlay blockers (query-time overlay)
  - circular-base erosion by base radius
- Build constrained triangulation + portal graph.
- Run A* over `(surface_id, portal_node_id)` state.
- Recover geometric path with funnel/string-pulling.
- Connector model for cross-layer movement:
  - ground<->floor
  - floor<->floor
  - fly-enabled transitions
  - breachable-wall transitions
- Each connector stores:
  - source/target surfaces
  - legal movement profiles
  - cost function
  - support-validation requirements
  - dynamic blocking status
- CDT backend requirement:
  - Prefer `shapely.constrained_delaunay_triangles` if available.
  - Current env is Shapely 2.0.6 (no constrained CDT), so implement fallback backend behind a narrow interface in `cdt_mesh.py` and add dependency as needed (do not leak backend details outside this module).

PHASE D — Local exact SE(2) corridor refinement
- Add `src/warhammer40k_ai/pathing/se2_refine.py`.
- Trigger refinement only when needed:
  - non-circular base
  - compound base
  - narrow corridor clearance near base dimensions
  - meaningful start/end facing delta
  - narrow doorway/tunnel/opening transitions
- Corridor-relative state includes:
  - `s`, `lateral_offset`, `theta_bin`, `surface_id`, `pivot_used_flag`
- Use exact footprint at each candidate pose via existing base shape API.
- Validate at each sampled pose:
  - inside corridor free space
  - support coverage when on elevated/top surfaces
  - dynamic overlaps legality
  - wall/opening legality
- If best corridor fails refinement, try next-best corridor before returning unreachable.

PHASE E — Unified public API + callsite migration + legacy deletion
- Add:
  - `src/warhammer40k_ai/pathing/api.py`
  - `src/warhammer40k_ai/pathing/sweep.py`
  - `src/warhammer40k_ai/pathing/__init__.py`
- Public API in `api.py`:
  - `plan_model_path(query: PathQuery) -> PathResult`
  - `preview_model_path(query: PathQuery) -> PathResult`
  - `validate_final_pose(query: PathQuery, pose: Pose) -> ValidationResult`
  - `compute_swept_interactions(query: PathQuery, path: PathResult) -> SweepResult`
- `PathResult` must include:
  - `poses` (x,y,z,facing sequence)
  - `waypoints`
  - `distance_cost`
  - `pivot_cost`
  - `used_exact_refiner`
  - `moved_over_enemy_model_ids`
  - `failure_reason`
  - optional `debug_artifacts` (feature-flagged)
- Migrate all movement callsites to this API:
  - `src/warhammer40k_ai/units/unit_mixins/actions_movement_mixin.py`
  - `src/warhammer40k_ai/UI/dialogs/individual_model_movement_dialog.py`
  - `src/warhammer40k_ai/UI/game_ui.py`
  - `src/warhammer40k_ai/UI/phases/phase_manager.py`
  - `src/warhammer40k_ai/engine/game.py`
  - `src/warhammer40k_ai/engine/decision_handlers/movement.py`
- Remove pathing ownership from `src/warhammer40k_ai/utility/calcs.py`:
  - delete `ORIENTATIONS`
  - delete `OptimizedPathfindingEnvironment`
  - delete `distance_to_nearest_obstacle`
  - delete `adaptive_step_size`
  - delete `move_object`
  - delete `get_neighbors`
  - delete `a_star_optimized_enhanced`
  - delete `get_optimized_path`
  - delete `create_optimized_pathfinding_environment`
  - delete wrappers that only feed legacy optimized A*
  - delete old “optimized A* 3–10x improvement” commentary block
  - move current unified planner out of `calcs.py` into `pathing/` and update all imports/callers

PHASE F — Swept-footprint rule checks
- Replace centerline moved-over detection with swept shape checks.
- `sweep.py` must provide:
  - `swept_footprint(path.poses) -> Polygon | MultiPolygon`
  - `intersects_enemy_models(swept_shape)`
  - `list_models_moved_over(swept_shape)`
- Circular: capsule-like or sampled union.
- Oval/hull/rotating: sampled-pose union with adaptive refinement by angle delta and narrow-clearance risk.
- Wire all Fall Back / Desperate Escape / move-over ability checks to sweep-based detection.

File-level edit list:
- Add package files:
  - src/warhammer40k_ai/pathing/api.py
  - src/warhammer40k_ai/pathing/types.py
  - src/warhammer40k_ai/pathing/rules_profile.py
  - src/warhammer40k_ai/pathing/world_snapshot.py
  - src/warhammer40k_ai/pathing/surfaces.py
  - src/warhammer40k_ai/pathing/cdt_mesh.py
  - src/warhammer40k_ai/pathing/surface_graph.py
  - src/warhammer40k_ai/pathing/corridor.py
  - src/warhammer40k_ai/pathing/se2_refine.py
  - src/warhammer40k_ai/pathing/dynamic_overlay.py
  - src/warhammer40k_ai/pathing/sweep.py
  - src/warhammer40k_ai/pathing/cache.py
  - src/warhammer40k_ai/pathing/__init__.py
- Modify:
  - src/warhammer40k_ai/utility/calcs.py
  - src/warhammer40k_ai/battlefield/map.py
  - src/warhammer40k_ai/units/unit_mixins/actions_movement_mixin.py
  - src/warhammer40k_ai/UI/dialogs/individual_model_movement_dialog.py
  - src/warhammer40k_ai/UI/game_ui.py
  - src/warhammer40k_ai/UI/phases/phase_manager.py
  - src/warhammer40k_ai/engine/game.py
  - src/warhammer40k_ai/engine/decision_handlers/movement.py
  - src/warhammer40k_ai/engine/path_witness.py (consume new pose path + sweep legality invariants)
- Update docs:
  - docs/MOVEMENT_SYSTEM.md
  - docs/TIGHT_CLEARANCE_POLICY.md
  - docs/PATH_WITNESS_CONTRACT.md
  - docs/NETWORK_SAVELOAD_DESIGN.md (only if dialog-to-decision mapping changes)

Required new/updated tests before merge:
1. Mirror match blocker classification:
  - same faction + different armies classified correctly.
2. Low terrain transit:
  - <= free climb threshold does not force detour.
3. Low terrain support overhang:
  - ending on top requires full footprint support (reject overhang).
4. Oval through narrow doorway:
  - succeeds only with valid rotated pose sequence.
5. Hull in tunnel:
  - global corridor may exist, exact refiner rejects impossible rotation.
6. Circular common-case performance:
  - repeated queries on unchanged terrain are faster than legacy quantized baseline (mark slow; deterministic benchmark harness).
7. Fall Back moved-over detection:
  - swept footprint catches interactions centerline misses.
8. Multi-floor ruin:
  - legal connector routing only (ground<->floor, floor<->floor).

Testing commands (run and report):
- `python -m pytest tests/pathing/ -m "not integration"`
- `python -m pytest tests/test_movement_terrain_sweep.py tests/test_movement_vertical_and_fly.py tests/test_collision_detection.py -m "not integration"`
- `python -m pytest tests/ -m "not slow and not integration"`
- `python -m pytest tests/`

Submission/report requirements:
- Provide exact files changed.
- Confirm all legacy pathing symbols removed from `utility/calcs.py`.
- Report exact pytest command outputs: pass/fail + any skipped tests (skips require approval).
- Call out any unresolved ambiguity before coding (do not guess rules text).
