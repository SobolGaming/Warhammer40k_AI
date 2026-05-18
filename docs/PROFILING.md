# Profiling

Launch-time profiling is opt-in and writes diagnostic artifacts without changing gameplay state, RNG, DecisionRecords, or replay behavior. Budgeted solvers use deterministic work-unit budgets for gameplay fallback decisions, and headless reaction windows do not expire from wall-clock timers, so profiler overhead can increase wall-clock telemetry but must not reduce solver work or alter the selected trajectory.

## UI Runner

```bash
uv run python scripts/main.py \
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
uv run python scripts/run_headless_self_play.py \
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

When `--report-output` is used, the report includes profile artifact paths plus per-game
`deployment_search_metrics` snapshots. These snapshots record deterministic search counters such as
anchor attempts, fast/full validation calls, quick rejects, first-valid source, and per-unit
model-position cache hits/misses.

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
- `los.frame_context_build`
- `los.visibility_context`
- `los.segment_blocked_by_terrain`

When reading deployment/LoS profile output, note that headless deployment validation reuses the
candidate's generated model-position payload across fast deployment validation and Decision API
validation. Headless deployment also avoids terrain surface-height and strategic-facing calculation
during search; detailed payload refinement is retained for small units where floor selection can
change legality. Shooting and map-facing LoS now share `VisibilityFrameContext`, which caches
model-to-unit results and reuses per-model-pair STRtree candidate lists across all staged rays at
the same terrain/model/modifier revision. Per-segment cache support is optional and disabled by
default because the profiled self-play workload produced near-zero segment-cache reuse.

Visibility value metrics include `los.pair_strtree_candidates`, `los.segment_tests`,
`los.exact_predicate_calls`, `los.visible_stage.*`, `los.first_blocker_exits`,
`los.frame_context_cache_hit/miss`, and LOS/optional-segment-cache hit/miss counters. High-frequency
LOS counters are batched per model-pair before being published to the profiling collector, so their
`total` column is the authoritative count.

## Cache Invalidation

`Map.state_generation` increments when battlefield topology changes **and** when runtime state
changes that affect geometry/rules cache validity:

- model movement (`Model.set_location`)
- model wounds changing
- model destruction/removal
- phase transitions and battle-round advancement
- command-point changes
- active stratagem/rule effects that modify runtime legality

Visibility cache keys include this generation, and map mutations clear per-map enemy-model
collision caches, so generated geometry caches do not survive stale game-state transitions.

Static datasheet parsing now uses immutable cached `ParsedDatasheetRecord` snapshots (composition,
abilities, keywords, wargear, and options). `Unit` instances consume cloned copies from that cache
and keep mutable battlefield state locally.
