# Deployment Ranking Pipeline

This document defines the imitation/ranking path for deployment pregame decisions.

## Scope

Current trainable deployment decision types:
- `CHOOSE_DEPLOYMENT_ZONE`
- `SELECT_NEXT_DEPLOY_UNIT`

The pipeline consumes DecisionRecords with deterministic candidate metadata and chosen actions.

## Dataset build

Script:
- `scripts/build_deployment_ranking_dataset.py`

Input:
- DecisionRecord JSON list (or object with `records` list).

Output:
- normalized ranking dataset with:
  - `feature_keys`
  - `decisions[]` grouped by decision id
  - legal candidate rows and chosen labels

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
  - next deploy unit requests
- If ranker cannot score a request, deterministic heuristic fallback remains active.

## Headless usage

```bash
python scripts/run_headless_self_play.py \
  --games 100 \
  --deployment-ranker-model data/deployment_ranker_model.json \
  --output data/headless_self_play_ranked.json
```
