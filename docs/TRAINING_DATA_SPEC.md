# Training Data Specification

Manifest module:
- `src/warhammer40k_ai/engine/training_manifest.py`
  - façade over:
    - `training_manifest_schema.py`
    - `training_manifest_builder.py`
    - `training_manifest_io.py`
    - `training_manifest_validate.py`

CLI:
- `scripts/build_training_manifest.py`
- `scripts/annotate_decision_rewards.py`
- `scripts/build_deployment_ranking_dataset.py`
- `scripts/train_deployment_ranker.py`

Operational runbook:
- `docs/HEADLESS_SELF_PLAY_RUNBOOK.md`

Manifest fields:
- `manifest_version`
- `generated_at_utc`
- `source_tag`
- `total_records`
- `rules_bundle_ids`
- `descriptor_bundle_ids`
- `mission_descriptor_ids`
- `objective_descriptor_ids`
- `terrain_descriptor_ids`
- `deployment_descriptor_ids`
- `army_build_descriptor_ids`
- `tool_descriptor_ids`
- `decision_type_counts`
- `coverage`
- `gameplay_quality`
- `gate_requirements`
- `slice_filters`

Slice/filter fields:
- `slice_filters.rules_bundle_ids`
- `slice_filters.descriptor_bundle_ids`
- `slice_filters.mission_descriptor_ids`
- `slice_filters.objective_descriptor_ids`
- `slice_filters.terrain_descriptor_ids`
- `slice_filters.deployment_descriptor_ids`
- `slice_filters.army_build_descriptor_ids`
- `slice_filters.tool_descriptor_ids`

Filtering semantics:
- OR within one filter family
- AND across different filter families
- objective / terrain / tool filters match records that contain any requested descriptor in that family
- rules / descriptor-bundle / mission / deployment / army-build filters match exact ids

Coverage metrics:
- `records_with_semantic_candidate_metadata`
- `semantic_candidate_metadata_ratio`
- `records_with_relabel_status`
- `relabel_status_ratio`
- `deployment_related_records`
- `deployment_zone_choice_records`
- `declare_reserves_records`
- `select_next_deploy_unit_records`
- `scout_move_records`
- `deployment_move_records`
- `deployment_records_with_semantic_metadata`
- `deployment_semantic_metadata_ratio`
- `has_deployment_zone_choice_coverage`
- `has_declare_reserves_coverage`
- `has_select_next_deploy_unit_coverage`
- `has_scout_move_coverage`
- `has_deployment_move_coverage`

Gameplay-quality metrics:
- `games_observed`
- `records_with_game_id`
- `records_with_game_id_ratio`
- `total_tactical_decisions`
- `minimum_tactical_decisions_per_game`
- `mean_tactical_decisions_per_game`
- `combat_decisions`
- `combat_decision_ratio`
- `games_with_score_snapshots`
- `games_with_score_snapshots_ratio`
- `games_with_scoring_progress`
- `scoring_progress_game_ratio`
- `no_progress_game_ratio`
- `games_with_combat_or_scoring_activity`
- `combat_or_scoring_active_game_ratio`
- `games_with_nontrivial_vp`
- `nontrivial_vp_game_ratio`
- `minimum_nontrivial_total_vp`

Gate requirements:
- `minimum_tier3_pretraining_records`
- `meets_minimum_tier3_pretraining_records`
- `semantic_candidate_metadata_required`
- `semantic_candidate_metadata_complete`
- `deployment_semantic_metadata_required`
- `deployment_semantic_metadata_complete`
- `gate_profile_id`
- `gate_profile_minimum_tier3_pretraining_records`
- `required_semantic_candidate_metadata_ratio`
- `required_relabel_status_ratio`
- `required_deployment_semantic_metadata_ratio`
- `gate_profile_minimum_games_observed`
- `required_records_with_game_id_ratio`
- `gate_profile_minimum_tactical_decisions_per_game`
- `required_combat_or_scoring_active_game_ratio`
- `maximum_no_progress_game_ratio`
- `required_nontrivial_vp_game_ratio`
- `minimum_nontrivial_total_vp`
- `meets_gate_profile_minimum_tier3_pretraining_records`
- `meets_required_semantic_candidate_metadata_ratio`
- `meets_required_relabel_status_ratio`
- `meets_required_deployment_semantic_metadata_ratio`
- `meets_gate_profile_minimum_games_observed`
- `meets_required_records_with_game_id_ratio`
- `meets_gate_profile_minimum_tactical_decisions_per_game`
- `meets_required_combat_or_scoring_active_game_ratio`
- `meets_maximum_no_progress_game_ratio`
- `meets_required_nontrivial_vp_game_ratio`
- `meets_gate_profile`

Canonical pre-ML gate profile:
- `gate_profile_id`: `pre_ml_baseline_v1`
- `minimum_tier3_pretraining_records`: `10000`
- required semantic metadata coverage ratio: `1.0`
- required relabel status coverage ratio: `1.0`
- minimum games observed: `20`
- required records-with-`game_id` ratio: `1.0`
- minimum tactical decisions per game: `25`
- required combat-or-scoring active game ratio: `0.8`
- maximum no-progress game ratio: `0.2`
- required nontrivial VP game ratio: `0.8`
- minimum nontrivial total VP per game: `5`
- CI gate policy: run manifest CLI with `--enforce-gate-profile` and fail pipeline if gate profile checks do not pass.

CLI example:

```bash
uv run python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest.json \
  --source-tag mixed \
  --min-tier3-records 10000
```

Filtered slice example:

```bash
uv run python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest_gladius.json \
  --source-tag mixed \
  --rules-bundle-id rules_bundle:preview_11e \
  --army-build-descriptor-id army_build_descriptor:gladius_slice \
  --tool-descriptor-id tool_descriptor:stratagem:armor_of_contempt
```

CI gate example:

```bash
uv run python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest.json \
  --source-tag mixed \
  --enforce-gate-profile
```

Reward annotation example:

```bash
uv run python scripts/annotate_decision_rewards.py \
  --input data/decision_records_relabeled.json \
  --output data/decision_records_rewarded.json \
  --reward-profile dense_vp_delta_v1
```

Repository CI wiring:
- GitHub Actions workflow `/.github/workflows/ci.yml` runs the enforced gate command on push/PR using a deterministic relabeled fixture dataset.

Validation policy:
- manifest must include all required top-level fields
- `decision_type_counts` sum must equal `total_records`
- semantic metadata coverage count cannot exceed total record count
- relabel coverage count cannot exceed total record count
- coverage ratios must match coverage counts
- gate thresholds must be non-negative
- gameplay-quality ratios must match their underlying game counts
- gate profile enforces gameplay-quality health so low-information/self-play-stalled datasets are rejected before ML training

Purpose before ML libraries:
- lock dataset structure and gate checks at the engine boundary
- make retraining scope auditable by rules/descriptor provenance
- make slice definitions auditable by rules bundle, army-build descriptor, and descriptor-family provenance
- prevent silent regressions in candidate-semantic coverage
- prevent low-information self-play corpora (for example repeated no-progression/near-0-0 games) from entering training
- keep reward shaping explicit and profile-versioned (`docs/TRAINING_REWARD_PROFILES.md`)

## Safe Pre-11th Training Policy

Allowed before final 11th rules land:
- Tier 3 micro-executors
- candidate-level movement, targeting, and fight-order scorers
- deterministic tool-usage policies conditioned on `rules_bundle_id`, `descriptor_bundle_id`, and descriptor families

Deferred until final 11th rules land:
- Tier 1 strategic planners
- mission-wide planning policies tied to current objective geometry
- deployment rankers that internalize the old mission system as canonical
- list-building agents

## Deployment imitation/ranking artifacts

Dataset build example:

```bash
uv run python scripts/build_deployment_ranking_dataset.py \
  --input data/headless_self_play_decision_records_rewarded.json \
  --output data/deployment_ranking_dataset.json
```

Model training example:

```bash
uv run python scripts/train_deployment_ranker.py \
  --input data/deployment_ranking_dataset.json \
  --output data/deployment_ranker_model.json
```

Runtime usage (headless self-play):

```bash
uv run python scripts/run_headless_self_play.py \
  --games 50 \
  --deployment-ranker-model data/deployment_ranker_model.json \
  --output data/headless_self_play_ranked.json
```
