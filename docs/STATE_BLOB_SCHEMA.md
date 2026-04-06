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
- `units`

Design notes:
- Terrain geometry and terrain semantics are public and versioned.
- Objective markers and score sources are distinct concepts when the active mission pack requires that split.
- Objective entries now carry:
  - site geometry (`MARKER`, `POLYGON_FOOTPRINT`, or `KEYED_FEATURE`)
  - an explicit primary `control_region`
  - one or more explicit `score_sources`
- `army_build_state` carries public army-construction semantics plus the active `army_build_descriptor_id`.
- `army_build_state.players[*].detachment_points_summary.spent` is always present, while `budget` / `remaining` may be `null` until the roster has an authored detachment-point budget.
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
- `threat_flags.can_reach_enemy_engagement_this_turn`
- `threat_flags.can_reach_score_source_this_turn`

Version notes:
- `1.2.0` adds explicit objective-site geometry/control/scoring payloads for terrain-footprint and keyed-feature objective support.
