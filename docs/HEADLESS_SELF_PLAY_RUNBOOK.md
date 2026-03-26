# Headless Self-Play Runbook

This runbook shows how to generate headless AI-vs-AI DecisionRecords from army lists and evaluate dataset quality before any expensive ML training.

Related docs:
- `docs/TRAINING_DATA_SPEC.md`
- `docs/TRAINING_REWARD_PROFILES.md`
- `docs/DEPLOYMENT_RANKING_PIPELINE.md`

## Prerequisites

Install the base project dependencies:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e .
```

Optional ML dependencies are only needed for later model training code paths:

```bash
python -m pip install -e ".[ml]"
python -c "from warhammer40k_ai.ml import detect_ml_dependency_status; print(detect_ml_dependency_status().to_dict())"
```

## 1) Generate headless AI-vs-AI games from army lists

`run_headless_self_play.py` runs full setup (including deployment) and battle phases in headless mode, then exports DecisionRecords.
It uses the same local authoritative runtime/session shell as interactive local play (`LocalAuthoritativeRuntime` + `AuthoritativeSessionDriver`) so lifecycle progression stays on the shared command path.

```bash
python scripts/run_headless_self_play.py \
  --games 200 \
  --workers 4 \
  --reserve-policy forced_only \
  --max-reserves-arrival-seconds 10 \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --max-phase-steps 80 \
  --output data/headless_self_play_decision_records.json
```

Optional replay capture for UI playback:

```bash
python scripts/run_headless_self_play.py \
  --games 5 \
  --workers 2 \
  --reserve-policy forced_only \
  --max-reserves-arrival-seconds 10 \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --output data/headless_self_play_decision_records.json \
  --replay-dir data/headless_self_play_replays
```

When `--replay-dir` is enabled, each game writes a session directory:
- `data/headless_self_play_replays/<game_id>/manifest.json`
- `data/headless_self_play_replays/<game_id>/snapshot.json`
- `data/headless_self_play_replays/<game_id>/replay.sqlite3`

Use `--replay-keyframe-interval <N>` to control sparse replay keyframe density.
Use a fresh replay base directory for each generation run, or delete conflicting `<game_id>/` session directories first.

What `--max-phase-steps 80` means:
- It is a safety cap on battle-phase transitions per game after setup.
- If a game appears stuck and reaches this cap, the script fails fast instead of running forever.

By default, this script also applies reward annotation using `dense_vp_delta_v1`.

Throughput controls:
- `--workers <N>` runs games in parallel processes.
- `--seed-base <S>` makes per-game RNG deterministic (`S + game_index`) across runs.
- `--reserve-policy forced_only` avoids optional reserve declarations (default; faster and more stable).
- `--max-reserves-arrival-seconds <T>` hard-caps per-unit reserve-arrival brute force (default: `10` seconds, always <= 1 minute unless explicitly raised).

Logging controls:
- `--log-level INFO` shows normal engine progress logs; use `--log-level DEBUG` for verbose combat/debug output.
- Save-failure roll summaries such as `Saves: 3/6 failed ...` now log at `DEBUG`, not `ERROR`.
- `--log-phase-transitions` emits an `INFO` log whenever the observed setup/battle state changes.
- Each emitted phase-transition log is tagged with a stable per-game id, so multi-worker output stays attributable:
  - without `--seed-base`: `selfplay:000000`, `selfplay:000001`, ...
  - with `--seed-base 9000`: `selfplay:9000`, `selfplay:9001`, ...
- Phase-transition format:

```text
(selfplay:000000 pre-deployment setup_phase=DEPLOY_ARMIES)
(selfplay:000000 post-deployment player=1 battle_round=1 phase=COMMAND_PHASE step=PHASE_START)
```

Example:

```bash
python scripts/run_headless_self_play.py \
  --games 3 \
  --workers 3 \
  --log-level INFO \
  --log-phase-transitions \
  --player1-army army_lists/chaos_test_2.txt \
  --player2-army army_lists/aeldari_test_2.txt \
  --output data/headless_self_play_decision_records.json
```

Result summary:
- Single-game runs print the winner using the army-list stem plus final score, for example:

```text
Winners: {'chaos_test_2': <SCORE: 45 vs 32>}
```

- Multi-game runs print aggregate winner counts by army label plus per-game outcome details keyed by the stable game id.
- If `--replay-dir` is enabled, the run also prints the resolved replay-session base directory.

## 1a) Load a recorded game into the replay viewer

Open a replay session by stable session id:

```bash
python scripts/replay_viewer.py \
  --session-id selfplay:000000 \
  --replay-dir data/headless_self_play_replays
```

Or open the SQLite artifact directly:

```bash
python scripts/replay_viewer.py \
  --replay-path data/headless_self_play_replays/selfplay:000000/replay.sqlite3
```

Viewer controls:
- `Left` / `Right`: move by one decision
- `Shift+Left` / `Shift+Right`: move by ten decisions
- `PageUp` / `PageDown`: move by twenty-five decisions
- `Home` / `End`: jump to first or last decision
- `Esc`: quit

Viewer notes:
- Replay controls render in a separate floating dialog pane instead of the battlefield HUD, can be dragged from anywhere on the panel, and may hang partly off-screen while leaving a visible grab strip.
- Bottom action/dice panes are rebuilt for the selected replay decision on every seek, so stepping backward clears future log entries.
- Deployment `MOVE_UNIT` replay entries now expand into numbered `(x, y, z, facing)` model placements in the Replay Controls pane instead of only showing the anchor label.

## 2) Relabel records for target rules bundle (recommended for cross-version data)

If your source records were produced under older rules-pack identifiers, relabel before manifest gating:

```bash
python scripts/relabel_decision_records.py \
  --input data/headless_self_play_decision_records.json \
  --output data/headless_self_play_decision_records_relabeled.json \
  --core-rules-id unknown_core_rules \
  --rules-commentary-id unknown_rules_commentary \
  --mission-pack-id unknown_mission_pack \
  --terrain-pack-id unknown_terrain_pack \
  --dataslate-id unknown_dataslate \
  --points-id unknown_points \
  --faction-pack-id unknown_faction_pack \
  --detachment-pack-id unknown_detachment_pack
```

If you skip relabeling, ensure your records already contain `relabel_status` because the canonical gate requires full relabel coverage.

## 3) Annotate rewards (if needed)

If you generated raw records (for example with `--no-reward-annotation`) or want a different reward profile:

```bash
python scripts/annotate_decision_rewards.py \
  --input data/headless_self_play_decision_records_relabeled.json \
  --output data/headless_self_play_decision_records_rewarded.json \
  --reward-profile dense_vp_delta_v1
```

## 4) Build manifest and enforce quality gate

```bash
python scripts/build_training_manifest.py \
  --input data/headless_self_play_decision_records_rewarded.json \
  --output data/training_manifest.json \
  --source-tag self_play \
  --enforce-gate-profile
```

If this command exits non-zero, do not proceed to training. Fix data generation first.

## 5) Evaluate dataset quality (what pass/fail means)

The canonical gate profile (`pre_ml_baseline_v1`) currently enforces:
- minimum records: `10000`
- semantic candidate metadata ratio: `1.0`
- relabel status ratio: `1.0`
- deployment semantic metadata ratio (deployment-related records): `1.0`
- minimum games observed: `20`
- records-with-`game_id` ratio: `1.0`
- minimum tactical decisions per game: `25`
- combat-or-scoring active game ratio: `0.8`
- maximum no-progress game ratio: `0.2`
- nontrivial VP game ratio: `0.8`
- minimum nontrivial total VP per game: `5`

These checks are designed to reject low-information corpora (for example many stalled 0-0 style games with little tactical activity).

## 6) Quick inspection tips

After manifest generation, inspect:
- `gameplay_quality`
- `gate_requirements`

Example:

```bash
python -c "import json; m=json.load(open('data/training_manifest.json', encoding='utf-8')); print(json.dumps({'gameplay_quality': m['gameplay_quality'], 'gate_requirements': m['gate_requirements']}, indent=2, sort_keys=True))"
```

Interpretation:
- `gate_requirements.meets_gate_profile == true`: dataset is acceptable for baseline pre-ML training use.
- any `meets_* == false`: treat as a data-generation quality issue and regenerate/retune self-play settings.

## 7) Build and train deployment ranking policy

Extract deployment decision groups for imitation/ranking:

```bash
python scripts/build_deployment_ranking_dataset.py \
  --input data/headless_self_play_decision_records_rewarded.json \
  --output data/deployment_ranking_dataset.json
```

Train a linear ranker:

```bash
python scripts/train_deployment_ranker.py \
  --input data/deployment_ranking_dataset.json \
  --output data/deployment_ranker_model.json
```

Use trained deployment ranker in headless play:

```bash
python scripts/run_headless_self_play.py \
  --games 50 \
  --deployment-ranker-model data/deployment_ranker_model.json \
  --output data/headless_self_play_ranked.json
```
