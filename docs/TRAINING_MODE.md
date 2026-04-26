# AI Training Mode

Training mode creates short, one-decision situations for human imitation learning. A user sees a UI prompt,
chooses from legal candidates, the scenario resolves an evaluation for that single step, and the chosen
`action_id` is recorded for the relevant AI component.

Implemented stages:
- `shooting_phase`: user chooses a target and weapon profile for a generated shooting declaration.
- `deployment_reserves`: user chooses a reserves package for a generated 2000 point army.
- `mixed`: alternates between the implemented stages.

The mode uses existing decision types:
- `DECLARE_SHOTS` routes to `shooting_ranker`.
- `DECLARE_RESERVES` routes to `deployment_ranker`.

No new gameplay decision type is introduced. Training observations are not full-game `DecisionRecord`s; they are
one-step observation records that preserve the serialized `DecisionRequest`, legal candidates, chosen action id,
component name, evaluation reward, and a supervised-example payload. Full-game training still uses canonical
`DecisionRecord` telemetry.

## Run UI Training

```bash
python scripts/run_training_mode.py \
  --stage mixed \
  --situations 20 \
  --seed 100 \
  --output data/training_mode_observations.jsonl \
  --model-output data/training_mode_preference_model.json
```

The Pygame UI presents one situation at a time. Each click records the user choice, evaluates it against the
scenario profile, updates the lightweight preference model, and advances after the feedback panel.

## Run Headless Smoke Training

Headless mode is useful for tests and pipeline checks:

```bash
python scripts/run_training_mode.py \
  --stage shooting_phase \
  --situations 10 \
  --headless-auto-choice best \
  --output data/training_mode_observations.jsonl \
  --model-output data/training_mode_preference_model.json
```

`--headless-auto-choice` supports:
- `first`: first legal candidate.
- `best`: evaluator-best candidate.
- `random`: random legal candidate from the scenario seed.
- `model`: current preference model choice with first-legal fallback.

## Learning Artifact

`TrainingPreferenceModel` is deliberately framework-free. It updates per-component numeric metadata weights from
observed choices and rewards, then stores JSON under `--model-output`. This gives the project an immediate
learning loop without adding ML dependencies to core. Learned neural/LLM systems can consume the JSONL
observations later through the same component/action-id contract.

Each JSONL observation includes:
- `session_id`, `scenario_id`, `stage`, and `component_name`
- serialized `DecisionRequest`
- `chosen_action_id`
- legality flag
- evaluator feedback and normalized reward
- `supervised_example` for later model or LLM fine-tuning

## Scope

Training mode is intentionally bounded to one phase step or one pre-battle decision window at a time. It does
not replace headless self-play, replay relabeling, or authoritative full-game `DecisionRecord` generation.
