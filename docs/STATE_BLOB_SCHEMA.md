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
- The state must preserve enough structure for descriptor recompilation and cross-version relabeling.
- Hidden information remains hidden in player-perspective snapshots.

Perspective rules:
- Omniscient state includes full hidden/public information consistent with replay requirements.
- Player-observation state hides opponent hidden information and preserves only legal information for that player.
- Public geometry/state (terrain, objectives, control regions) is included for all players.

Derived deterministic feature examples:
- `in_engagement_range`
- `control_region_ids_in_range`
- `score_source_ids_in_range`
- `threat_flags.can_reach_enemy_engagement_this_turn`
- `threat_flags.can_reach_score_source_this_turn`
