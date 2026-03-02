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

Gate requirements:
- `minimum_tier3_pretraining_records`
- `meets_minimum_tier3_pretraining_records`
- `semantic_candidate_metadata_required`
- `semantic_candidate_metadata_complete`

CLI example:

```bash
python scripts/build_training_manifest.py \
  --input data/decision_records_relabeled.json \
  --output data/training_manifest.json \
  --source-tag mixed \
  --min-tier3-records 10000
```

Validation policy:
- manifest must include all required top-level fields
- `decision_type_counts` sum must equal `total_records`
- semantic metadata coverage count cannot exceed total record count
- gate thresholds must be non-negative

Purpose before ML libraries:
- lock dataset structure and gate checks at the engine boundary
- make retraining scope auditable by rules/descriptor provenance
- prevent silent regressions in candidate-semantic coverage
