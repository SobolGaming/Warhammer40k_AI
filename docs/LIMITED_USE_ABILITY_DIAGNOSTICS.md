# Limited-Use Ability Diagnostics

This diagnostic pass audits replay stores for optional ability decisions that consume a limited-use resource, especially once-per-battle abilities.

It does not change game legality or controller behavior. It is an analysis layer for detecting shallow policy behavior such as always choosing `Use` whenever an optional once-per-battle prompt appears.

## Decision Context Contract

Limited-use decisions should carry normalized context fields in addition to rule-specific payload:

- `limited_use=true`
- `limited_use_scope`: one of `battle`, `battle_per_model`, `battle_per_unit`, `battle_round`, `turn`, or `phase`
- `limited_use_key`: stable key for the consumed resource
- `once_per_battle=true`, `once_per_battle_key`, and `once_per_battle_scope` for once-per-battle abilities
- `once_per_battle_round_key`, `once_per_turn_key`, and `once_per_phase_key` are emitted for those shorter resource windows when available.
- Optional `limited_use_call_number` and `limited_use_max_uses` when an ability has multiple battle-scoped uses or a detachment grants an extra use.

The central decision queue path normalizes explicit limited-use metadata, legacy `once_key` context, and known optional confirmations such as `WAAAGH!` and `Shadow in the Warp` before a `DecisionRecord` is emitted. The diagnostics still detect older text-only, legacy-key, or known-key records such as old `fire_overwatch` selector rows, but report them as missing normalized metadata.

## CLI

Single report:

```bash
python3 scripts/analyze_limited_use_abilities.py \
  --report models/reports/example_run \
  --output models/reports/example_run/limited_use_ability_diagnostics.json \
  --primary-score-label Aeldari_Warhost_2000 \
  --opponent-score-label WE_Daemonkin_2000
```

Same-seed paired reports:

```bash
python3 scripts/analyze_limited_use_abilities.py \
  --baseline-report models/reports/heuristic_run \
  --candidate-report models/reports/candidate_run \
  --output models/reports/candidate_run/limited_use_ability_diagnostics.json \
  --primary-score-label Aeldari_Warhost_2000 \
  --opponent-score-label WE_Daemonkin_2000 \
  --baseline-name heuristic \
  --candidate-name v6
```

By default the pass includes `battle`, `battle_per_model`, and `battle_per_unit` scopes. Add `--limit-scope battle_round`, `--limit-scope turn`, or `--limit-scope phase` when auditing broader limited-use behavior.

Source-data scan:

```bash
python3 scripts/scan_limited_use_sources.py --no-entries
```

This scans `wahapedia_data/Abilities.json`, `wahapedia_data/Datasheets_abilities.json`, `wahapedia_data/Detachment_abilities.json`, `wahapedia_data/Stratagems.json`, and `wahapedia_data/Enhancements.json` for limited-use rules text. Omit `--no-entries` or pass `--output path/to/report.json` to inspect matching entries.

`FIRE OVERWATCH` is treated as a turn-scoped limited-use stratagem (`limited_use_scope="turn"`, `limited_use_key="fire_overwatch"`) because its restriction is once per turn. This keeps movement and charge reactive-window sequencing visible to replay audits and ML features.

## Output Shape

The report groups rows by:

- `ability_label`: decision type plus ability name/message.
- `ability_phase_round`: ability label plus phase and battle round.

Each bucket includes counts, use/skip rates, final-margin means for used versus skipped decisions, battle-round counts, and chosen label counts.

Top-level missing-metadata fields:

- `missing_limited_use_metadata_count`: limited-use decisions detected from prose or legacy keys without normalized context.
- `missing_limited_use_metadata_by_ability`: grouped view of those rows.

Each row includes `limited_use_metadata_present` and `limited_use_metadata_missing` so replay audits can distinguish clean new telemetry from older or incomplete records.

## Interpretation

These diagnostics show correlation, not full causality. A once-per-battle use in battle round 2 can affect score in battle round 5 through board-state changes that are not isolated by this pass.

Use this output to identify ability prompts that need richer opportunity-cost features, counterfactual replay probes, or human-reviewed labels before trusting a learned ranker.
