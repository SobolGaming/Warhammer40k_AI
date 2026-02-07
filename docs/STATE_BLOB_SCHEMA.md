# StateBlob Schema (Engine Foundation)

State blobs are deterministic JSON objects used for telemetry and replay-oriented decision logging.

Version:
- `state_blob_version` currently `1.0.0`

Top-level fields:
- `state_blob_version`
- `battle_round`
- `phase`
- `active_player_id`
- `players`
- `objectives`
- `units`

Perspective rules:
- Omniscient state includes full player mission-card names.
- Player-observation state hides opponent mission-card names and exposes counts only.
- Unit and objective geometry/state are public and included for all players.

Derived deterministic features included per unit:
- `in_engagement_range`
- `objective_ids_in_range`
- `threat_flags.can_reach_enemy_engagement_this_turn`
- `threat_flags.can_reach_objective_this_turn`
