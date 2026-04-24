# Profiling

Launch-time profiling is opt-in and writes diagnostic artifacts without changing gameplay state, RNG, DecisionRecords, or replay behavior.

## UI Runner

```bash
python scripts/main.py \
  --profile \
  --profile-dir profiles \
  --profile-label ui_baseline
```

Useful options:

- `--profile`: enables cProfile plus section timers.
- `--profile-dir`: output directory, default `profiles`.
- `--profile-sort`: pstats sort key, default `tottime`.
- `--profile-lines`: readable report row count, default `120`.
- `--profile-label`: filename label prefix.

The UI runner dumps profiles on normal exit, `KeyboardInterrupt`, and the existing logged error path.

## Headless Self-Play

```bash
python scripts/run_headless_self_play.py \
  --games 4 \
  --workers 4 \
  --profile \
  --profile-dir profiles \
  --profile-label headless_baseline \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --output data/headless_self_play_decision_records.json
```

Each game job writes its own readable `.txt` report and binary `.prof` file. In multi-worker runs, profiling happens inside worker processes so the artifacts include the actual game work instead of only parent-process orchestration. Filenames include a safe version of the game id and process id; the report metadata keeps the exact game id.

When `--report-output` is used, the report includes profile artifact paths only.

## Report Contents

Readable reports include:

- run metadata: script, PID, game id when available, elapsed wall time, sort key, and output paths
- cProfile output sorted by `--profile-sort`
- regex hotspot counters
- section timers with `calls`, `total_ms`, `avg_ms`, and `max_ms`

The binary `.prof` files can be opened with standard pstats-compatible tools such as `python -m pstats`, SnakeViz, or Tuna.

## Section Timers

Section timers are inclusive domain timers. cProfile remains the source of truth for exact function-level self time and cumulative call stacks.

Initial section timers cover:

- `deployment.generate_candidates`
- `deployment.headless_build_move_candidates`
- `deployment.prospective_model_positions`
- `deployment.position_validation`
- `movement.generate_candidates`
- `movement.payload_validation`
- `movement.path_plan`
- `movement.final_pose_validation`
- `movement.transit_validation`
- `movement.swept_interactions`
- `los.visibility_context`
- `los.segment_blocked_by_terrain`

When reading deployment/LoS profile output, note that headless deployment validation reuses the
candidate's generated model-position payload across fast deployment validation and Decision API
validation, and both terrain-service and legacy shooting-mixin LoS checks are cached for repeated
checks of the same model pair at the same positions and terrain/blocker state. Section timer call
counts should therefore be interpreted as cache miss/work counts rather than every high-level
shooting or deployment policy probe.

## Cache Invalidation

`Map.state_generation` increments when terrain, objectives, or placed units change. Visibility
cache keys include this generation, and map mutations clear per-map enemy-model collision caches,
so generated geometry caches do not survive battlefield topology changes.
