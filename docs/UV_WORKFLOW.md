# uv Workflow

This repository uses `uv` for local development and CI dependency management.
Use the project-local `.venv` created by `uv sync`; do not install project
dependencies into the system Python or a global user site.

## Install uv

Install uv with the official standalone installer for your platform:

<https://docs.astral.sh/uv/getting-started/installation/>

## Environment Setup

From the repository root:

```bash
uv sync --extra test
```

For UI work:

```bash
uv sync --extra test --extra ui --extra ui-test
```

For optional ML-boundary work:

```bash
uv sync --extra ml
```

## Running Commands

Run commands through uv so imports and console scripts resolve from the
repo-local environment:

```bash
uv run python -m pytest tests/ -m "not slow and not integration"
uv run python scripts/run_headless_self_play.py --games 1 --workers 1
uv run warhammer40k-ai --version
```

## Ranker Diagnostics

Before ranker training, extract diagnostic candidate rows and a coverage report
from DecisionRecords or profile-eval record outputs:

```bash
uv run python scripts/extract_ranker_training_rows.py \
  --input data/general_profile_eval/mirror_eval \
  --output-jsonl data/ranker_training_rows.jsonl \
  --coverage-output data/ranker_training_coverage.json \
  --ui-smoke-status pass \
  --network-smoke-status pass \
  --snapshot-smoke-status pass
```

The JSONL output is candidate-row oriented and intended for inspection before
training. The coverage report summarizes decision counts, candidate counts,
mask ratio, chosen-action rank, commander assignment/fallback signals, stale
plan signals, resource authorization status, context payload size, deployment
tempo usage, and smoke pass/fail status. When `--input` points at a directory,
the extractor scans decision-record-like filenames such as
`decision_records.json`, `accepted_decision_records.json`, and
`*_records.json`; unrelated JSON artifacts such as snapshots and summaries are
ignored. Pass an explicit JSON/JSONL file path when a nonstandard filename
should be consumed.

General profile evaluation can write the same diagnostics while producing its
compact matrix report:

```bash
uv run python scripts/run_general_profile_eval.py \
  --pairing-mode mirror \
  --write-records \
  --write-ranker-diagnostics \
  --output-dir data/general_profile_eval/mirror_eval \
  --ui-smoke-status pass \
  --network-smoke-status pass \
  --snapshot-smoke-status pass
```

For deterministic ranker weight sweeps before ML, run fixed-seed profile
matrices across configured component-ranker weight sets:

```bash
uv run python scripts/run_ranker_weight_sweep.py \
  --weight-sets data/ranker_weight_sweeps/example_weight_sets.json \
  --pairing-mode mirror \
  --output-dir data/ranker_weight_sweeps/mirror_eval \
  --ui-smoke-status pass \
  --network-smoke-status pass \
  --snapshot-smoke-status pass
```

The sweep report compares every weight set to the baseline and links the
per-weight-set matrix report plus ranker row/coverage artifacts. Analyze the
result before promoting any candidate:

```bash
uv run python scripts/analyze_ranker_weight_sweep.py \
  --input data/ranker_weight_sweeps/mirror_eval/weight_sweep_report.json \
  --output data/ranker_weight_sweeps/mirror_eval/weight_sweep_analysis.json \
  --min-vp-delta 1.0 \
  --min-win-delta 1
```

The analysis ranks candidates by VP differential, win/loss/tie counts,
fallback-rate delta, commander-hit-rate delta, stale-plan-rate delta,
resource-usage anomalies, context-size regressions, and decision/phase-count
regressions.

Promotion is explicit and produces a checked-in artifact without changing
engine defaults:

```bash
uv run python scripts/promote_ranker_weight_candidate.py \
  --analysis data/ranker_weight_sweeps/mirror_eval/weight_sweep_analysis.json \
  --promoted-weight-set-id score_pressure_baseline_v1 \
  --output data/ranker_weight_sweeps/promoted_baselines/score_pressure_baseline_v1.json
```

## UI Smoke Checks

The script-level smokes are also available as a repeatable pytest lane:

```bash
uv run python -m pytest tests/smoke/ -m smoke
```

These tests are marked `smoke`, `integration`, and `slow`; UI and network
entries are additionally marked `ui` and `network`.

For pygame UI boot coverage without opening a real window, use SDL's dummy
video driver. The smoke script initializes the local authoritative runtime,
publishes `game_loaded`, advances setup to the manual deployment boundary,
builds deployment plans, resolves one manual deployment selection through the
local decision path, draws a few frames, and exercises ESC/SPACE/resize events.
It is a crash smoke only; it does not verify rendering quality.

```bash
SDL_VIDEODRIVER=dummy uv run python scripts/smoke_ui_local.py \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt
```

PowerShell:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
uv run python scripts/smoke_ui_local.py `
  --player1-army army_lists/chaos_test.txt `
  --player2-army army_lists/aeldari_test.txt
```

For network loopback coverage, run the two-client smoke. It starts a localhost
server on an ephemeral port, handshakes two clients, submits army lists, starts
the game, loads snapshots into `NetworkGameSession`, waits for setup/formation
traffic, resolves all formation decisions needed to enter `DEPLOY_ARMIES`,
initializes network deployment, resolves one deployment selection, asserts no
`ErrorMessage` payloads, asserts no unexpected resync storm, and stops both
clients and the server cleanly before reporting success.

```bash
uv run python scripts/smoke_network_loopback.py \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt
```

PowerShell:

```powershell
uv run python scripts/smoke_network_loopback.py `
  --player1-army army_lists/chaos_test.txt `
  --player2-army army_lists/aeldari_test.txt
```

For compiled orchestration context persistence coverage, run the snapshot plan
smoke. It forces `GeneralPlan`, `DeploymentOrderBundle`,
`PreBattleOrderBundle`, `DeploymentPlan`, `BattleRoundPlan`, and
`CommanderOrderBundle` context onto a pending deployment request, serializes the
snapshot with `json.dumps`, reloads it, and snapshots the loaded game again.

```bash
uv run python scripts/smoke_snapshot_plans.py \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt
```

PowerShell:

```powershell
uv run python scripts/smoke_snapshot_plans.py `
  --player1-army army_lists/chaos_test.txt `
  --player2-army army_lists/aeldari_test.txt
```

## Lockfile Policy

`uv.lock` is checked in. Update it whenever `pyproject.toml` dependencies,
extras, build metadata, or supported Python bounds change:

```bash
uv lock
```

If your machine is behind endpoint security or a managed TLS root store and
uv reports `UnknownIssuer`, use OS certificates:

```bash
uv --system-certs lock
uv --system-certs sync --extra test
```

CI uses `uv sync --frozen`, so dependency changes without a matching lockfile
update should fail early.
