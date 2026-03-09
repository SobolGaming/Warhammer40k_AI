# Deployment Ranking Pipeline

This document defines the imitation/ranking path for deployment pregame decisions.

## Scope

Current trainable deployment decision types:
- `CHOOSE_DEPLOYMENT_ZONE`
- `DECLARE_RESERVES`
- `SELECT_NEXT_DEPLOY_UNIT`
- `SCOUT_MOVE`
- `MOVE_UNIT` (deployment-only: `placement_kind="deployment"`)

Default candidate kinds used for dataset extraction:
- `deployment_zone`
- `deployment_commit_order`
- `deployment_reserves`
- `deployment_scout`
- `deployment_move`
- `noop` (skip/pass candidates in deployment-scoped requests)

The pipeline consumes DecisionRecords with deterministic candidate metadata and chosen actions.
Deployment-zone candidates include board-affordance metadata produced from terrain-aware lane
sampling (for example `los_tunnel_count`, `hidden_staging_cell_count`,
`must_expose_to_advance_cell_count`, infantry/vehicle approach quality).

## Dataset build

Script:
- `scripts/build_deployment_ranking_dataset.py`
- Supports `--decision-types` and `--candidate-kinds` filters for controlled extraction.

Input:
- DecisionRecord JSON list (or object with `records` list).

Output:
- normalized ranking dataset with:
  - `feature_keys`
  - `candidate_kinds`
  - `decisions[]` grouped by decision id
  - legal candidate rows and chosen labels
- `MOVE_UNIT` records are included only when `context.placement_kind == "deployment"`.

## Model training

Script:
- `scripts/train_deployment_ranker.py`

Model:
- `deployment_linear_ranker_v1`
- linear score over normalized candidate metadata
- pairwise logistic optimization (chosen vs non-chosen candidates)

Output model includes:
- `feature_keys`
- `weights`, `bias`
- normalization vectors (`mean`, `scale`)
- allowed `decision_types` and `candidate_kinds`
- training metrics (`pairwise_accuracy`, `top1_accuracy`, sample counts)

## Runtime integration

- `DeterministicDeploymentDecisionMaker` accepts `ranker_model_path`.
- When provided, it prefers ranker-based option selection for:
  - deployment zone choice requests
  - reserves allocation requests
  - next deploy unit requests
  - scout move requests (through the shared deployment solver metadata path)
- If ranker cannot score a request, deterministic heuristic fallback remains active.

## Headless usage

```bash
python scripts/run_headless_self_play.py \
  --games 100 \
  --deployment-ranker-model data/deployment_ranker_model.json \
  --output data/headless_self_play_ranked.json
```
