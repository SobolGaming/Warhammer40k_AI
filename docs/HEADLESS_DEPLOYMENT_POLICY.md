# Headless Deployment Policy

This document describes deterministic headless placement behavior for deployment and reserves-arrival decisions.

## Deployment (Headless Decision Maker)

- `DeterministicDeploymentDecisionMaker` remains legality-first and deterministic.
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
  - When loaded, zone, reserves-allocation, and next-unit choices can be selected directly from request candidates via ranker scores.
  - If model scoring is unavailable for a request, deterministic heuristic fallback remains active.
- Standard units:
  - Candidate anchors are searched inside the assigned deployment zone.
  - Teacher semantic anchors are evaluated first, then lattice fallback scanning.
- Units with `Infiltrators`:
  - Candidate anchors are searched in-zone first, then expanded to board-wide candidates.
  - Final legality is still enforced by deployment validation (`enemy zone`, `9"` enemy zone buffer, `9"` enemy model buffer, terrain legality).

## Ruins Floors (Headless Deployment Payloads)

- Headless deployment now generates floor-aware placement payload variants.
- For RUINS footprints, candidate model `z` values include valid floor surfaces (`elevation + thickness`) in addition to ground.
- Variant ordering is deterministic and prefers elevated legal placements before ground fallback.
- Final acceptance still uses the engine's decision validation path.

## Reserves Arrival Candidate Generation

- `HeadlessPolicyDecisionController` now uses an adaptive, deterministic anchor strategy:
  - Strategic reserves:
    - Edge-biased anchors around preferred edge offsets.
    - Staggered along-edge scans.
    - Sparse fallback edge bands and guaranteed corner anchors.
  - Non-strategic reserves arrival:
    - Adaptive coarse-to-fine board scans with staggered lattices.
- A cheap prefilter rejects clearly impossible strategic anchors (deep interior points) before expensive placement synthesis.
- Anchor generation remains deterministic and bounded by `max_reserves_anchor_points`.

## Pregame Decision Surfaces

- `DECLARE_RESERVES` now emits deterministic multi-option allocation candidates (forced-only, pressure, balanced variants) with semantic metadata.
- `SCOUT_MOVE` now emits deterministic destination options (plus skip) and solver metadata keyed to reserve denial, entry-lane quality, and exposure.
- Deployment-scoped `MOVE_UNIT` candidates continue to carry exact-model placement payloads and deployment semantic metadata.
