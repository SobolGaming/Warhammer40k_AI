# Headless Deployment Policy

This document describes deterministic headless placement behavior for deployment and reserves-arrival decisions.

## Deployment (Headless Decision Maker)

- `DeterministicDeploymentDecisionMaker` remains legality-first and deterministic.
- Default headless deployment is now a deterministic fast-packer:
  - deployment order prefers large-footprint / low-flex units before small screens when rules do not force another order;
  - exact placement generation stops at a small bounded candidate set by default (`top_k=2`);
  - semantic/ranker/lookahead scoring remains active, but only as a tie-break across that bounded candidate set.
- Deployment search now reuses a cached occupancy snapshot per board state instead of rebuilding terrain/blocker geometry for every anchor.
  - terrain blockers, boundary repulsors, live blocker polygons, and the Shapely `STRtree` are built once per search;
  - unit formation templates are cached by model count and spacing.
- The headless decision maker now uses a deterministic heuristic pregame teacher (`PregameDeploymentAgent`) when player context is available.
  - Deployment zone choice is teacher-scored from army-role inference and board affordances.
  - Board affordances include terrain-agnostic LOS/route signals (not RUINS-only), including
    LOS tunnel pressure, hidden staging cells, exposure pressure, and per-objective approach quality.
  - `SELECT_NEXT_DEPLOY_UNIT` order is teacher-scored instead of implicit roster order.
  - Deployment intent/context payloads are enriched with:
    - `army_role_summary`
    - `board_affordances`
    - tuned deployment weights/affordances for the current player and zone.
- Reserve choices in `balanced` mode still obey reserve limits and validation, but candidate ranking now includes teacher reserve preference scoring.
- Optional imitation/ranking model integration:
  - `DeterministicDeploymentDecisionMaker(..., ranker_model_path=...)` can load a linear deployment ranker model.
  - When loaded, zone, reserves-allocation, next-unit, scout, and deployment-placement choices can be selected directly from request candidates via ranker scores.
  - If model scoring is unavailable for deployment placement requests and rollout metadata is present, the headless policy can fall back to `lookahead_total_value` candidate selection.
  - If neither model nor rollout scoring is available, deterministic heuristic fallback remains active.
- Deployment-manager-owned setup requests (`CHOOSE_DEPLOYMENT_ZONE`, `DECLARE_RESERVES`,
  `SELECT_NEXT_DEPLOY_UNIT`, and deployment `MOVE_UNIT`) are resolved by `DeploymentManager`/
  `DeploymentDecisionMaker`, not by the generic `HeadlessPolicyDecisionController`.
- Teacher decision context now includes optional rollout settings under `deployment_lookahead`
  (enabled, depth, branch count, discount, blend, candidate kinds) for bounded pregame lookahead.
- Standard units:
  - Candidate anchors are searched inside the assigned deployment zone with packing-first rows/gaps before lattice fallback scanning.
  - Teacher semantic anchors are still evaluated, but they no longer force an unbounded exact-placement search.
- Units with `Infiltrators`:
  - Candidate anchors are searched in-zone first, then expanded to board-wide candidates.
  - Final legality is still enforced by deployment validation (`enemy zone`, `9"` enemy zone buffer, `9"` enemy model buffer, terrain legality).
- If a unit still produces no legal deployment placements after candidate generation/validation, the
  engine logs a warning, skips battlefield placement, and removes the unit from play instead of
  crashing the whole headless run.
- Deployment diagnostics are available from `DeterministicDeploymentDecisionMaker.get_deployment_search_metrics()`.
  - Per-unit metrics include deployment order, anchor attempts, quick rejects, validation calls, calls to first valid result, returned candidate count, first-valid anchor source, exhaustive fallback usage, and elapsed wall-clock time.

## Ruins Floors (Headless Deployment Payloads)

- Headless deployment now generates floor-aware placement payload variants.
- For RUINS footprints, candidate model `z` values include valid floor surfaces (`elevation + thickness`) in addition to ground.
- Variant ordering is deterministic and prefers elevated legal placements before ground fallback.
- Final acceptance still uses the engine's decision validation path.

## Reserves Arrival Candidate Generation

- `HeadlessPolicyDecisionController` now uses an adaptive, deterministic fast-packer anchor strategy:
  - Strategic reserves:
    - edge-biased anchors around preferred edge offsets;
    - staggered along-edge scans;
    - sparse fallback edge bands and guaranteed corner anchors.
  - Non-strategic reserves arrival:
    - board landmarks, open-gap anchors, then adaptive coarse-to-fine board scans with staggered lattices.
- A cheap prefilter rejects clearly impossible anchors before expensive placement synthesis.
  - board bounds;
  - strategic edge-band depth;
  - enemy-distance envelopes;
  - anchor-range envelopes for source-unit-based arrivals.
- Exact reserve model-position synthesis now delegates to the shared `reserve_entry_geometry.py`
  helper so headless reserve landing generation stays aligned with the authoritative reserve-entry
  validation seam.
- Anchor generation remains deterministic and bounded by `max_reserves_anchor_points`.
- Reserves diagnostics are available from `HeadlessPolicyDecisionController.get_reserves_arrival_search_metrics()`.
  - Per-decision metrics include anchor attempts, quick rejects, build calls, calls to first valid result, first-valid anchor source, exhaustive fallback usage, and elapsed wall-clock time.

## Benchmark Workflow

- Setup-only headless benchmark helper:
  - `warhammer40k_ai.engine.headless_setup_benchmark.run_setup_only_headless_benchmark(...)`
- Local benchmark CLI:
  - `python scripts/benchmark_headless_setup.py --player1-army army_lists/Aeldari_Warhost_2000.txt --player2-army army_lists/WE_Daemonkin_2000.txt --output data/headless_setup_benchmark.json`
- Optional before/after comparison:
  - pass `--baseline-json <path>` to compare current output against a previously captured benchmark JSON.
- Benchmark output includes:
  - per-setup-phase timings;
  - per-unit deployment diagnostics;
  - reserves-arrival synthetic benchmark cases for crowded Deep Strike and strategic-reserve edge entry;
  - aggregated summaries for validation calls, fallback usage, and first-valid anchor sources.

## Pregame Decision Surfaces

- `DECLARE_RESERVES` now emits deterministic multi-option allocation candidates (forced-only, pressure, balanced variants) with semantic metadata.
- `SCOUT_MOVE` now emits deterministic destination options (plus skip) and solver metadata keyed to reserve denial, entry-lane quality, and exposure.
- Deployment-scoped `MOVE_UNIT` now emits deterministic multi-option exact-placement candidates at runtime (anchor + exact `model_positions` per option), with per-option deployment semantic metadata.
- With rollout enabled, deployment pregame candidates include deterministic shallow-lookahead metadata (`lookahead_*`) and adjusted round/trade projections for ranker consumption.
