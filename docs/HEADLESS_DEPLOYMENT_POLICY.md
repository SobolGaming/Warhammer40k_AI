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
- Headless deployment candidate validation now reuses the prospective model positions generated for
  each anchor when calling both `Game.is_valid_deployment_position(...)` and the authoritative
  `MOVE_UNIT` Decision API validation. This avoids recomputing formation placement for the same
  candidate during setup profiling runs.
- Standard deployment quick-rejects use the estimated packed unit width/depth when rejecting anchors
  near deployment-zone edges, which prevents large multi-model units from invoking full placement
  synthesis for obviously edge-clipped anchors.
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
- Reserve choices in `forced_only` mode still keep ordinary optional units deployed. If an army has more than two oversized/Titanic deployment footprints, the policy may place validated overflow units into Strategic Reserves so crowded headless deployments do not destroy large models before the game starts.
- Optional imitation/ranking model integration:
  - `DeterministicDeploymentDecisionMaker(..., ranker_model_path=...)` can load a linear deployment ranker model.
  - When loaded, zone, reserves-allocation, next-unit, scout, and deployment-placement choices can be selected directly from request candidates via ranker scores.
  - If model scoring is unavailable for deployment placement requests and rollout metadata is present, the headless policy can fall back to `lookahead_total_value` candidate selection.
  - If neither model nor rollout scoring is available, deterministic heuristic fallback remains active.
- Deployment-manager-owned setup requests (`CHOOSE_DEPLOYMENT_ZONE`, `DECLARE_RESERVES`,
  `SELECT_NEXT_DEPLOY_UNIT`, and deployment `MOVE_UNIT`) are resolved by `DeploymentManager`/
  `DeploymentDecisionMaker`, not by the generic `HeadlessPolicyDecisionController`.
- Alternating deployment filters out units that are already deployed, embarked in transports, currently
  in reserves/strategic reserves, attached leaders, joined support units, or forced to start in reserves
  before placement candidate generation. This keeps transport passengers and reserve-start units from
  consuming battlefield placement searches or being destroyed as skipped deployments.
- Teacher decision context now includes optional rollout settings under `deployment_lookahead`
  (enabled, depth, branch count, discount, blend, candidate kinds) for bounded pregame lookahead.
- Standard units:
  - Candidate anchors are searched inside the assigned deployment zone with packing-first rows/gaps before lattice fallback scanning.
  - Teacher semantic anchors are still evaluated, but they no longer force an unbounded exact-placement search.
- Units with `Infiltrators`:
  - Candidate anchors are searched in-zone first, then expanded to board-wide candidates.
  - Final legality is still enforced by deployment validation (`enemy zone`, `9"` enemy zone buffer, `9"` enemy model buffer, terrain legality).
- If a headless unit still produces no legal deployment placements after candidate
  generation/validation, `DeterministicDeploymentDecisionMaker` moves it into
  validated reserve-start state with `reserve_source=deployment_overflow` instead
  of destroying it during setup. Non-headless decision makers can still decline
  recovery, in which case the deployment manager logs the existing warning and
  removes the unit from play instead of crashing the run.
- Deployment diagnostics are available from `DeterministicDeploymentDecisionMaker.get_deployment_search_metrics()`.
  - Per-unit metrics include deployment order, anchor attempts, quick rejects, validation calls, fast-validation rejects, calls to first valid result, returned candidate count, first-valid anchor source, exhaustive fallback usage, and elapsed wall-clock time.
  - If all normal anchor groups are rejected, deployment runs one deterministic relaxed fallback search that bypasses conservative occupied-unit quick-rejects, still rejects edge-impossible anchors, and caps the relaxed scan. This is intended for crowded deployments where a coarse anchor bounding-box test can be too pessimistic for multi-model units without letting impossible placements dominate runtime.

## Ruins Floors (Headless Deployment Payloads)

- Headless deployment now generates floor-aware placement payload variants.
- For RUINS footprints, candidate model `z` values include valid floor surfaces (`elevation + thickness`) in addition to ground.
- Variant ordering is deterministic and prefers elevated legal placements before ground fallback.
- Final acceptance still uses the engine's decision validation path.

## Reserves Arrival Candidate Generation

- `HeadlessPolicyDecisionController` now uses an adaptive, deterministic fast-packer anchor strategy:
  - preserve the strongest reserve-specific anchors first:
    - Deep Strike / non-strategic arrivals still probe board landmarks before broader scans;
    - Strategic reserves still probe the primary edge-band anchors before broader scans.
  - then reuse the same zone-based packing heuristics used by pre-game deployment, but against reserve-legal search zones:
    - Deep Strike search applies deployment-style row packers over battlefield sectors plus a bounded battlefield lattice;
    - Strategic reserves apply deployment-style row packers over legal edge-band zones;
    - units in Strategic Reserves that can also Deep Strike search edge-band zones first, then battlefield Deep Strike zones.
  - Strategic reserves:
    - edge-biased anchors around preferred edge offsets;
    - large single-model bases use orientation-aware edge offsets from the model's actual circular,
      oval, hull, or compound footprint bounds instead of a generic longest-radius offset; when the
      oriented perpendicular footprint cannot fit wholly within 6", generated anchors touch the
      battlefield edge exactly without clipping over it or drifting away from it;
    - those large edge-touch arrivals add a bounded dense along-edge scan before staggered fallback
      so aircraft can find narrow legal gaps around terrain and deployed models;
    - battle round 2 Strategic Reserves arrivals reject any placement whose model base has
      positive-area overlap with the enemy deployment zone, even if the model centre is outside it;
    - AIRCRAFT reserve arrivals keep boundary, overlap, enemy-distance, and reserve-edge checks,
      but do not reject otherwise legal airborne setup solely because the projected base footprint
      intersects RUINS wall/floor surface geometry;
    - deployment-style row packers over legal edge bands;
    - staggered along-edge scans;
    - sparse fallback edge bands and guaranteed corner anchors.
  - Non-strategic reserves arrival:
    - board landmarks first;
    - deployment-style row packers over battlefield sectors plus a bounded battlefield lattice;
    - open-gap anchors, then adaptive coarse-to-fine board scans with staggered lattices.
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
  - Per-decision metrics include anchor attempts, quick rejects, build calls, calls to first valid result, first-valid anchor source, exhaustive fallback usage, failure reason, timeout status, and elapsed wall-clock time.
  - Failed reserve-arrival searches write `reserve_last_arrival_failure` back to the unit as structured metadata (`reason`, anchor/build/reject counters, timeout flag, elapsed milliseconds). State blobs expose this metadata for hidden state and for the owning player's observation.
- Reserve-arrival requests include reserve provenance in context:
  - `reserve_source` (`must_start_in_reserves` or `deployment_choice`)
  - `reserve_mandatory_start`
  - `reserve_latest_arrival_round`
  - `reserve_last_arrival_failure`
- Reserve-start mutations route through shared metadata helpers so units that started
  in reserves cannot retain blank `reserve_source` or `reserve_latest_arrival_round=0`.
  If a post-deployment check has to repair incomplete metadata, it records
  `reserve_metadata_incomplete_post_deployment` in `reserve_arrival_diagnostics`.
- Forced arrivals still search legal reserve zones first. If every generated placement is rejected, the
  controller resolves the same `MOVE_UNIT` request through an explicit `Unable to arrive`
  fallback option. This is not a voluntary pass: the unit remains in reserves and existing
  end-of-battle-round destruction rules handle units that still have not arrived.
- Before the Reinforcements step is allowed to close, the turn manager rechecks unresolved mandatory
  reserve arrivals and requeues the deterministic `SELECT_UNIT` request if any remain. Optional reserve
  passes still end normally; this guard is only for units that must arrive this step.

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

## Self-Play Diagnostics

- `scripts/run_headless_self_play.py --report-output <path>` writes per-game
  `tool_action_probe_diagnostics`, `reserve_arrival_diagnostics`, and
  `reserves_arrival_search_metrics` into the JSON report.
- The runner prints a per-game tool-probe diagnostic summary grouped by
  severity, tool name, and code. Candidate-build filtering caused by missing
  required stratagem/ability context is logged as `WARNING`. A shared tool-action
  preflight firewall filters emitted specs that fail descriptor-derived
  eligibility, entity-reference roundtrip resolution, or final `can_use(...)`
  validation before exposing `SELECT_TOOL_ACTION`; those diagnostics use
  `illegal_tool_candidate_filtered_preflight` or
  `malformed_tool_candidate_filtered_preflight`. Any malformed tool
  candidate that reaches execute/apply is logged as `ERROR` with
  `malformed_tool_candidate_escaped_preflight`.
- Units destroyed at the battle round 3 reserves cutoff emit
  `reserve_destroyed_round3` diagnostics with reserve provenance and the last
  failed placement reason, when one was recorded.
- `scripts/run_headless_matchup_batch.py` keeps `reserve_destroyed_round3`
  entries in the reserve-arrival diagnostic totals, but does not elevate that
  documented warning into the `Errors / Bug Candidates` report section. Other
  reserve-arrival diagnostics remain reportable bug candidates.

## Pregame Decision Surfaces

- `DECLARE_RESERVES` now emits deterministic multi-option allocation candidates (forced-only, pressure, balanced variants) with semantic metadata.
- If no legal reserve allocation exists, strict request-builder calls raise an
  explicit roster/setup legality error instead of exposing an invalid fallback
  option; formation-phase orchestration suppresses the request rather than
  queuing malformed options for empty or temporarily unrepresentable setup
  states.
- `SCOUT_MOVE` now emits deterministic destination options plus skip, including exact translated `model_positions` for generated scout choices so headless resolution can apply the selected endpoint without invoking full surface-graph pathfinding. Validation still requires destination coordinates and rejects generated endpoints that exceed Scout distance or end within 9" of enemy models. If no legal destination can be generated, the request emits only skip rather than an invalid placeholder Scout action.
- Deployment-scoped `MOVE_UNIT` now emits deterministic multi-option exact-placement candidates at runtime (anchor + exact `model_positions` per option), with per-option deployment semantic metadata.
- With rollout enabled, deployment pregame candidates include deterministic shallow-lookahead metadata (`lookahead_*`) and adjusted round/trade projections for ranker consumption.
