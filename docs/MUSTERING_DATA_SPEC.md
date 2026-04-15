# Mustering Data Spec

This document defines the PR-MUSTER-008 telemetry layer for roster mustering,
roster search, and tournament-roster evaluation experiments.

Related implementation files:
- `src/warhammer40k_ai/roster/muster_record.py`
- `src/warhammer40k_ai/roster/muster_manifest.py`
- `scripts/build_mustering_manifest.py`
- `src/warhammer40k_ai/ml/evaluation_pipeline.py`

## Purpose

Mustering data is the reusable experiment corpus for future learned
list-building. It is deliberately separate from `DecisionRecord` training data:
`DecisionRecord` captures in-game actions, while `MusterRecord` captures roster
candidate provenance, utility, search edits, and evaluation gates.

The current schema ids are:
- `muster_record_schema:v1`
- `mustering_manifest_schema:v1`

Schema version changes are explicit. Runtime loaders reject unknown
`muster_record_schema_id`, `muster_record_version`,
`mustering_manifest_schema_id`, and `manifest_version` values instead of
silently adapting them.

## MusterRecord

`MusterRecord` is one roster experiment row. A row can represent a tournament
evaluation result or a roster-search candidate.

Required lineage fields:
- `army_blueprint_hash`
- `rules_bundle_id`
- `capability_schema_id`
- `build_capability_profile_id`
- `field_distribution_id`
- `event_policy_id`
- `policy_bundle_id`
- `controller_bundle_id`

Optional but expected provenance fields:
- `descriptor_bundle_id`
- `descriptor_provenance`
- `provenance.git_commit`
- `report_paths`

Evaluation and search fields:
- `utility_terms` stores decomposed objective terms such as VP margin, replay
  pass rate, gate state, and controller-complexity components.
- `replay_gate_outcomes` stores replay audit, manifest gate, self-play status,
  and failure reasons.
- `search_edit_sequence` stores ordered roster edit actions for search
  candidates. Empty means the record was not produced by a roster-search edit
  path.

## MusteringManifest

`MusteringManifest` summarizes a corpus or filtered slice of `MusterRecord`
rows. It is the file used to audit and reuse experiment corpora.

It records:
- total rows and record kind counts
- `record_ids` in row order, preserving duplicates when a corpus intentionally
  contains repeated experiments or the same input file is supplied more than
  once
- all rules, capability, build profile, field, event-policy, policy-bundle, and
  controller-bundle ids represented in the slice
- faction and detachment tags represented in the slice
- numeric utility term summaries
- replay/gate outcome summaries
- search edit summaries
- provenance rollups such as git commits, evaluation modes, and report dirs

Supported slice filters:
- `rules_bundle_id`
- `capability_schema_id`
- `field_distribution_id`
- `event_policy_id`
- `policy_bundle_id`
- `controller_bundle_id`
- `faction`
- `detachment_type`
- `faction_tag`
- `detachment_tag`
- `record_kind`
- `army_blueprint_hash`
- `build_capability_profile_id`

## CLI

Build a manifest from one or more record files:

```bash
python3 scripts/build_mustering_manifest.py \
  --input models/reports/run_a/muster_record.json \
  --input models/reports/run_b/muster_record.json \
  --output models/mustering_corpora/april/mustering_manifest.json \
  --corpus-id mustering_corpus:april \
  --source-tag mixed
```

Build a rules/event/policy slice:

```bash
python3 scripts/build_mustering_manifest.py \
  --input models/mustering_corpora/april/records.json \
  --output models/mustering_corpora/april/slice_space_marines.json \
  --corpus-id mustering_corpus:april_space_marines \
  --source-tag mixed \
  --rules-bundle-id rules_bundle:munitorum_2026_04 \
  --event-policy-id event_policy:chapter_approved_10e_singles_v1 \
  --field-distribution-id field_distribution:gt_2026_04 \
  --policy-bundle-id policy_bundle:heuristic_eval_v1 \
  --faction-tag "Space Marines" \
  --detachment-tag "Gladius Task Force"
```

The CLI validates input `MusterRecord` rows before summarizing and validates the
output `MusteringManifest` before writing it.

## Tournament Evaluation Reports

`scripts/evaluate_tournament_roster.py` writes these mustering artifacts next to
the existing evaluation reports:
- `muster_record.json`
- `mustering_manifest.json`

`summary.json` links to both files through:
- `roster_evaluation.muster_record_path`
- `roster_evaluation.mustering_manifest_path`
- `roster_evaluation.muster_record_id`
- `roster_evaluation.lineage`

The lineage block includes the rules bundle, build capability profile,
capability schema, field distribution, event policy, policy bundle, and policy
bundle descriptor scope used for the run.

## Example Muster Record

```json
{
  "army_blueprint_hash": "army_blueprint:4f52d28c98e1",
  "build_capability_profile_id": "build_capability_profile:space_marines_gladius_v1",
  "capability_schema_id": "capability_schema:build_capability_v1",
  "controller_bundle_id": "policy_bundle:heuristic_eval_v1",
  "descriptor_bundle_id": "descriptor_bundle:chapter_approved_2026_04",
  "descriptor_provenance": {
    "descriptor_bundle_id": "descriptor_bundle:chapter_approved_2026_04",
    "event_policy_id": "event_policy:chapter_approved_10e_singles_v1",
    "field_distribution_id": "field_distribution:gt_2026_04",
    "policy_bundle_id": "policy_bundle:heuristic_eval_v1",
    "rules_bundle_id": "rules_bundle:munitorum_2026_04"
  },
  "detachment_tags": [
    "Gladius Task Force"
  ],
  "detachment_type": "Gladius Task Force",
  "event_policy_id": "event_policy:chapter_approved_10e_singles_v1",
  "faction": "Space Marines",
  "faction_tags": [
    "Imperium",
    "Space Marines"
  ],
  "field_distribution_id": "field_distribution:gt_2026_04",
  "generated_at_utc": "2026-04-15T00:00:00Z",
  "metadata": {
    "candidate_roster_label": "space_marines_gladius"
  },
  "muster_record_schema_id": "muster_record_schema:v1",
  "muster_record_version": "1.0.0",
  "policy_bundle_id": "policy_bundle:heuristic_eval_v1",
  "provenance": {
    "evaluation_mode": "headless_fixed",
    "git_commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "record_id": "muster_record:example",
  "record_kind": "evaluation",
  "replay_gate_outcomes": {
    "failure_reasons": [],
    "manifest_gate": {
      "passed": true
    },
    "replay_audit": {
      "passed": true
    },
    "success": true
  },
  "report_paths": {
    "report_dir": "models/reports/tournament_roster_eval_example"
  },
  "rules_bundle_id": "rules_bundle:munitorum_2026_04",
  "search_edit_sequence": [],
  "source_tag": "tournament_roster_evaluation",
  "utility_terms": {
    "candidate_mean_vp": 74.5,
    "candidate_win_rate": 0.625,
    "mean_vp_margin": 8.25,
    "replay_pass_rate": 1.0
  }
}
```

## Example Mustering Manifest

```json
{
  "army_blueprint_hashes": [
    "army_blueprint:4f52d28c98e1"
  ],
  "build_capability_profile_ids": [
    "build_capability_profile:space_marines_gladius_v1"
  ],
  "capability_schema_ids": [
    "capability_schema:build_capability_v1"
  ],
  "controller_bundle_ids": [
    "policy_bundle:heuristic_eval_v1"
  ],
  "corpus_id": "mustering_corpus:example",
  "detachment_tags": [
    "Gladius Task Force"
  ],
  "detachment_types": [
    "Gladius Task Force"
  ],
  "event_policy_ids": [
    "event_policy:chapter_approved_10e_singles_v1"
  ],
  "faction_tags": [
    "Imperium",
    "Space Marines"
  ],
  "factions": [
    "Space Marines"
  ],
  "field_distribution_ids": [
    "field_distribution:gt_2026_04"
  ],
  "generated_at_utc": "2026-04-15T00:00:00Z",
  "manifest_version": "1.0.0",
  "mustering_manifest_schema_id": "mustering_manifest_schema:v1",
  "outcome_summary": {
    "failure_reason_counts": {},
    "gate_passed_count": 1,
    "gate_passed_ratio": 1.0,
    "replay_passed_count": 1,
    "replay_passed_ratio": 1.0,
    "success_count": 1,
    "success_ratio": 1.0
  },
  "policy_bundle_ids": [
    "policy_bundle:heuristic_eval_v1"
  ],
  "provenance_summary": {
    "evaluation_modes": [
      "headless_fixed"
    ],
    "git_commits": [
      "0123456789abcdef0123456789abcdef01234567"
    ],
    "report_dirs": [
      "models/reports/tournament_roster_eval_example"
    ]
  },
  "record_ids": [
    "muster_record:example"
  ],
  "record_kind_counts": {
    "evaluation": 1
  },
  "record_schema": {
    "muster_record_schema_id": "muster_record_schema:v1",
    "muster_record_version": "1.0.0"
  },
  "rules_bundle_ids": [
    "rules_bundle:munitorum_2026_04"
  ],
  "search_summary": {
    "edit_action_id_counts": {},
    "edit_action_type_counts": {},
    "records_with_search_edits": 0,
    "total_search_edit_count": 0
  },
  "slice_filters": {
    "army_blueprint_hashes": [],
    "build_capability_profile_ids": [],
    "capability_schema_ids": [],
    "controller_bundle_ids": [],
    "detachment_tags": [],
    "detachment_types": [],
    "event_policy_ids": [],
    "faction_tags": [],
    "factions": [],
    "field_distribution_ids": [],
    "policy_bundle_ids": [],
    "record_kinds": [],
    "rules_bundle_ids": []
  },
  "source_tag": "tournament_roster_evaluation",
  "total_records": 1,
  "utility_term_summary": {
    "candidate_mean_vp": {
      "count": 1,
      "max": 74.5,
      "mean": 74.5,
      "min": 74.5
    },
    "candidate_win_rate": {
      "count": 1,
      "max": 0.625,
      "mean": 0.625,
      "min": 0.625
    },
    "mean_vp_margin": {
      "count": 1,
      "max": 8.25,
      "mean": 8.25,
      "min": 8.25
    },
    "replay_pass_rate": {
      "count": 1,
      "max": 1.0,
      "mean": 1.0,
      "min": 1.0
    }
  }
}
```
