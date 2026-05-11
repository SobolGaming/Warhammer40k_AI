# Limited-Use Ability Diagnostics

This diagnostic pass audits replay stores for optional ability decisions that consume a limited-use resource, especially once-per-battle abilities.

It does not change game legality or controller behavior. It is an analysis layer for detecting shallow policy behavior such as always choosing `Use` whenever an optional once-per-battle prompt appears.

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

## Output Shape

The report groups rows by:

- `ability_label`: decision type plus ability name/message.
- `ability_phase_round`: ability label plus phase and battle round.

Each bucket includes counts, use/skip rates, final-margin means for used versus skipped decisions, battle-round counts, and chosen label counts.

## Interpretation

These diagnostics show correlation, not full causality. A once-per-battle use in battle round 2 can affect score in battle round 5 through board-state changes that are not isolated by this pass.

Use this output to identify ability prompts that need richer opportunity-cost features, counterfactual replay probes, or human-reviewed labels before trusting a learned ranker.
