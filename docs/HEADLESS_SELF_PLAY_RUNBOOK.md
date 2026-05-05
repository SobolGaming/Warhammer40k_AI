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
python -m pip install -e ".[test]"
```

Optional ML dependencies are only needed for later model training code paths:

```bash
python -m pip install -e ".[ml]"
python -c "from warhammer40k_ai.ml import detect_ml_dependency_status; print(detect_ml_dependency_status().to_dict())"
```

Optional LLM-backed domain agents do not require an SDK dependency. Provide a JSON config with a
local or remote Chat Completions compatible endpoint, then pass
`--llm-agent-config <path>` to self-play. See `docs/LLM_AGENT_RUNTIME.md`.

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

LLM-backed self-play example:

```bash
python scripts/run_headless_self_play.py \
  --games 10 \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --llm-agent-config data/llm_agent_config.json \
  --output data/llm_self_play_decision_records.json
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

When `--replay-dir` is enabled, each game writes a filesystem-safe session directory under the replay root.
The replay session id normally matches the stable per-game `game_id`, and the folder name uses a deterministic
path-safe encoding when needed (for example `selfplay:000000` becomes `selfplay~3A000000` on disk):
- `data/headless_self_play_replays/<session_dir>/manifest.json`
- `data/headless_self_play_replays/<session_dir>/snapshot.json`
- `data/headless_self_play_replays/<session_dir>/replay.sqlite3`

Use `--replay-keyframe-interval <N>` to control sparse replay keyframe density.
If a prior run already created the preferred replay session id, the script now auto-suffixes the replay session
id (`selfplay:000000:run001`, `selfplay:000000:run002`, ...) instead of failing. DecisionRecords still keep the
stable per-game `game_id`, while the machine-readable report records the actual replay session id in
`replay_session_id`.

What `--max-phase-steps 80` means:
- It is a safety cap on battle-phase transitions per game after setup.
- If a game appears stuck and reaches this cap, the script fails fast instead of running forever.

By default, this script also applies reward annotation using `dense_vp_delta_v1`.

Throughput controls:
- `--workers <N>` runs games in parallel processes.
- `--seed-base <S>` makes per-game RNG deterministic (`S + game_index`) across runs.
- `--reserve-policy forced_only` avoids ordinary optional reserve declarations (default; faster and more stable), but can still reserve validated oversized/Titanic overflow units when too many large footprints would otherwise fail deployment.
- `--max-reserves-arrival-seconds <T>` hard-caps per-unit reserve-arrival brute force (default: `10` seconds, always <= 1 minute unless explicitly raised).

Default shooting policy:
- Headless `DECLARE_SHOTS` synthesis declares one legal profile for each ranged weapon carried by an eligible model.
- Hazardous profiles are eligible during default shooting.
- For weapons with multiple legal targetable profiles, the controller chooses the profile/target pair with the best hit-probability x wound-probability, using expected damage only as a tie-breaker.
- Generic headless `SELECT_REALM_OF_CHAOS_UNITS` handling now synthesizes deterministic `unit_ids`
  for required unit-selection windows, such as Siege Regiment `Creeping Barrage`, and answers
  optional empty-selection windows with their skip option instead of attempting an invalid empty confirm.
- Genestealer Cults Outlander Claw `CLOSE-RANGE SHOOT-OUT` derives eligible Mounted/Vehicle units that have not been selected to shoot before exposing the generic stratagem tool action, so target-required options are not emitted without a bound unit.
- Core `GRENADE` and `TANK SHOCK` expose one generic stratagem tool action per legal unit/enemy binding when CP is available, including windows with multiple legal enemy targets.
- Automatic headless `HEROIC INTERVENTION` tool actions are bounded to direct charge routes, avoiding expensive opportunistic routed-path searches during reaction probes.
- Aeldari Seer Council phase items populate legal source, model, enemy, and shooting-target context for `PRESENTIMENT OF DREAD`, `FATE INESCAPABLE`, and `UNSHROUDED TRUTH` before any headless tool-action preflight.
- Post-command headless stratagem tool-action scans are gated until setup is complete, so deployment commands cannot trigger normal battle-phase stratagem candidate generation through the default command-phase placeholder.
- T'au Kauyon `POINT-BLANK AMBUSH` / `WALL OF MIRRORS` and Imperial Agents Veiled Blade `PRIME TARGET` use faction-specific tool-action preflight so the headless controller only sees legal timing and target candidates.
- Selected-to-fight stratagems such as Imperial Agents Veiled Blade `PRIME TARGET` are exposed from the
  `fight_unit_selected` reaction window, not from broad Fight phase scans, so Fight phase records are not
  polluted by stratagem prompts when no unit has actually been selected to fight.
- Chaos Space Marines Deceptors `COILS OF DECEPTION` and related Fall Back-only CSM stratagems are treated
  as reaction-only tool actions, so broad Movement phase scans do not emit invalid options before a unit has
  actually ended a Fall Back move.

Pending-placement policy:
- Headless `MOVE_UNIT` confirmations that represent pending model placement (for example Reanimation Protocols or other confirm-only deploy-style follow-up placements) now synthesize explicit `model_positions` before resolution.
- When the greedy reanimation placement heuristic leaves the unit out of coherency, the headless controller performs a bounded deterministic backtracking search over legal placement candidates and emits the first coherent placement it finds.
- Synthesized reanimation placements now pass the same RUINS wall/floor validation used by authoritative movement handling, so headless placement candidates do not later fail on terrain legality.
- Deployment candidate builders that produce no usable structured placements now fall back to deterministic anchor placement instead of silently dropping battlefield placement for the unit.
- Headless deployment candidate generation now builds a friendly-aware placement search context, so multi-model pack layouts avoid already deployed friendly units instead of emitting overlap-only payloads that later fail authoritative validation.
- When the exact deployment anchor cannot synthesize a legal multi-model pack, the headless deployer performs a bounded deterministic local anchor jitter search before giving up on that candidate.
- Late-game small-unit deployment fallback now searches deeper half-inch home-corner and perimeter bands before giving up, which keeps edge-crowded units up to five models from missing legal deployment slots.
- Strategic Reserves aircraft and other large single-model bases use base-touching edge offsets when their footprint cannot fit wholly within 6" of an edge. AIRCRAFT reserve arrivals keep boundary/overlap/enemy checks but ignore RUINS wall/floor surface geometry for the airborne setup footprint, and the Movement phase requeues unresolved mandatory reserve arrivals before closing the Reinforcements step.
- `model_destroyed_before_removal` reaction prompts now normalize `destroyed_model` / `destroyed_unit` into standard tool-action bindings, which keeps destroyed-model stratagems such as `PROTOCOL OF THE ETERNAL REVENANT` available in headless play.
- The accepted per-model placement payload is recorded in both DecisionRecords and replay storage, so playback and reconstruction can reproduce the completed placement without relying on UI-only state.

Logging controls:
- `--log-level INFO` shows normal engine progress logs; use `--log-level DEBUG` for verbose combat/debug output.
- Save-failure roll summaries such as `Saves: 3/6 failed ...` now log at `DEBUG`, not `ERROR`.
- Battle-shock failure status lines and Shadow of Chaos Daemonic Terror mortal-wound resolution also log at `DEBUG`, not `ERROR`.
- Failed charge movement, including automatic headless Heroic Intervention attempts, logs below `WARNING`; failed charges are normal game outcomes, not engine errors.
- Deadly Demise parameters that are fixed numbers, for example `Deadly Demise 1`, are treated as fixed
  mortal-wound damage instead of dice expressions.
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

Profiling controls:
- `--profile` enables per-game cProfile and section-timer reports.
- `--profile-dir profiles` chooses the output directory.
- `--profile-sort tottime` and `--profile-lines 120` control the readable pstats summary.
- `--profile-label <label>` adds a filename prefix for baseline/comparison runs.
- In multi-worker runs, each worker game job writes its own `.txt` and `.prof` artifacts.

Example:

```bash
python scripts/run_headless_self_play.py \
  --games 4 \
  --workers 4 \
  --profile \
  --profile-label movement_baseline \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --output data/headless_self_play_decision_records.json \
  --report-output data/headless_self_play_report.json
```

The optional machine-readable report records profile artifact paths only; timing details stay in the profile logs.
See `docs/PROFILING.md` for report contents and section timer names.

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
  --replay-path data/headless_self_play_replays/selfplay~3A000000/replay.sqlite3
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
