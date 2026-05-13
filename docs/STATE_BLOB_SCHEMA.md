# StateBlob Schema (Engine Foundation)

State blobs are deterministic, versioned JSON objects used for telemetry, replay, relabeling, and feature extraction.

Version:
- `state_blob_version` is semver and increments when structure changes.

Top-level fields:
- `state_blob_version`
- `rules_bundle`
- `battle_round`
- `phase`
- `active_player_id`
- `players`
- `army_build_state`
- `mission_state`
- `deployment_state`
- `objectives`
- `scoring_surfaces`
- `control_regions`
- `terrain`
- `detection_markers`
- `hidden_shooting_exemptions`
- `units`

Design notes:
- Terrain geometry and terrain semantics are public and versioned.
- `terrain` entries can now represent both terrain features and terrain areas via `runtime_kind`.
- `detection_markers` lists preview-gated detection-range marker state, including marker label,
  source unit, target unit, range delta, duration, detachment/source provenance, and enabled profile.
- `hidden_shooting_exemptions` lists preview-gated unit exemptions that preserve Hidden after shooting.
- Objective markers and score sources are distinct concepts when the active mission pack requires that split.
- Objective entries now carry:
  - site geometry (`MARKER`, `POLYGON_FOOTPRINT`, or `KEYED_FEATURE`)
  - an explicit primary `control_region`
  - one or more explicit `score_sources`
  - sticky-control metadata including any minimum Level of Control floor
  - optional `terrain_area_id` / `layout_slot_id` bindings
- `army_build_state` carries public army-construction semantics plus the active `army_build_descriptor_id`.
- `army_build_state.players[*].detachment_points_summary.spent` is always present, while `budget` / `remaining` may be `null` until the roster has an authored detachment-point budget.
- Hidden state and owning-player observation unit entries expose reserve provenance:
  `reserve_source`, `reserve_mandatory_start`, `reserve_latest_arrival_round`,
  and structured `reserve_last_arrival_failure` metadata alongside
  `reserve_status`.
- The state must preserve enough structure for descriptor recompilation and cross-version relabeling.
- Hidden information remains hidden in player-perspective snapshots.
- The generator is split across `state_blob_rules.py`, `state_blob_players.py`, `state_blob_mission.py`, `state_blob_objectives.py`, `state_blob_terrain.py`, and `state_blob_units.py`, with `state_blob.py` kept as the stable facade.

Perspective rules:
- Omniscient state includes full hidden/public information consistent with replay requirements.
- Player-observation state hides opponent hidden information and preserves only legal information for that player.
- Public geometry/state (terrain, objectives, control regions, army-build state) is included for all players.

Derived deterministic feature examples:
- `in_engagement_range`
- `control_region_ids_in_range`
- `score_source_ids_in_range`
- `model_positions` for alive on-battlefield models, including model id, base pose, base type, and radii
- `threat_flags.can_reach_enemy_engagement_this_turn`
- `threat_flags.can_reach_score_source_this_turn`
- `threat_flags.nearest_enemy_base_distance`
- `threat_flags.nearest_score_source_base_distance`

Unit entries do not expose a synthetic unit centroid. Unit geometry is represented
with per-model base positions, and derived tactical distances are based on model/base
edge distances to enemy bases or objective control regions. Units that are embarked,
in reserves, or otherwise not on the battlefield have no model-position footprint for
objective/control computations.

Version notes:
- `1.2.0` adds explicit objective-site geometry/control/scoring payloads for terrain-footprint and keyed-feature objective support.
- `1.3.0` adds persisted objective sticky-control minimum Level of Control support.
- `1.4.0` adds terrain-area entries, explicit terrain/runtime kind tagging, and objective/layout terrain-area identifiers.
- `1.5.0` adds reserve provenance and last-arrival-failure metadata to unit entries.
- `1.6.0` removes centroid-derived unit `position` from unit entries, adds per-model
  base positions, and changes tactical threat flags to use model/base edge distances.
- `1.7.0` adds preview-gated `detection_markers` and `hidden_shooting_exemptions` top-level entries.
