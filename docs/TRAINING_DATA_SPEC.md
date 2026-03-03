# Training Data Specification

Manifest module:
- `src/warhammer40k_ai/engine/training_manifest.py`

CLI:
- `scripts/build_training_manifest.py`
- `scripts/annotate_decision_rewards.py`

Manifest fields:
- `manifest_version`
- `generated_at_utc`
- `source_tag`
- `total_records`
- `rules_bundle_ids`
- `descriptor_bundle_ids`
- `decision_type_counts`
- `coverage`
- `gameplay_quality`
- `gate_requirements`

Coverage metrics:
- `records_with_semantic_candidate_metadata`
- `semantic_candidate_metadata_ratio`
- `records_with_relabel_status`
- `relabel_status_ratio`

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
- `gate_profile_id`
- `gate_profile_minimum_tier3_pretraining_records`
- `required_semantic_candidate_metadata_ratio`
- `required_relabel_status_ratio`
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
python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest.json \
  --source-tag mixed \
  --min-tier3-records 10000
```

CI gate example:

```bash
python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest.json \
  --source-tag mixed \
  --enforce-gate-profile
```

Reward annotation example:

```bash
python scripts/annotate_decision_rewards.py \
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
- prevent silent regressions in candidate-semantic coverage
- prevent low-information self-play corpora (for example repeated no-progression/near-0-0 games) from entering training
- keep reward shaping explicit and profile-versioned (`docs/TRAINING_REWARD_PROFILES.md`)
