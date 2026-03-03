# Training Data Specification

Manifest module:
- `src/warhammer40k_ai/engine/training_manifest.py`

CLI:
- `scripts/build_training_manifest.py`

Manifest fields:
- `manifest_version`
- `generated_at_utc`
- `source_tag`
- `total_records`
- `rules_bundle_ids`
- `descriptor_bundle_ids`
- `decision_type_counts`
- `coverage`
- `gate_requirements`

Coverage metrics:
- `records_with_semantic_candidate_metadata`
- `semantic_candidate_metadata_ratio`
- `records_with_relabel_status`
- `relabel_status_ratio`

Gate requirements:
- `minimum_tier3_pretraining_records`
- `meets_minimum_tier3_pretraining_records`
- `semantic_candidate_metadata_required`
- `semantic_candidate_metadata_complete`
- `gate_profile_id`
- `gate_profile_minimum_tier3_pretraining_records`
- `required_semantic_candidate_metadata_ratio`
- `required_relabel_status_ratio`
- `meets_gate_profile_minimum_tier3_pretraining_records`
- `meets_required_semantic_candidate_metadata_ratio`
- `meets_required_relabel_status_ratio`
- `meets_gate_profile`

Canonical pre-ML gate profile:
- `gate_profile_id`: `pre_ml_baseline_v1`
- `minimum_tier3_pretraining_records`: `10000`
- required semantic metadata coverage ratio: `1.0`
- required relabel status coverage ratio: `1.0`
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

Repository CI wiring:
- GitHub Actions workflow `/.github/workflows/ci.yml` runs the enforced gate command on push/PR using a deterministic relabeled fixture dataset.

Validation policy:
- manifest must include all required top-level fields
- `decision_type_counts` sum must equal `total_records`
- semantic metadata coverage count cannot exceed total record count
- relabel coverage count cannot exceed total record count
- coverage ratios must match coverage counts
- gate thresholds must be non-negative

Purpose before ML libraries:
- lock dataset structure and gate checks at the engine boundary
- make retraining scope auditable by rules/descriptor provenance
- prevent silent regressions in candidate-semantic coverage
