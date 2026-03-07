# Headless Deployment Policy

This document describes deterministic headless placement behavior for deployment and reserves-arrival decisions.

## Deployment (Headless Decision Maker)

- `DeterministicDeploymentDecisionMaker` remains legality-first and deterministic.
- Standard units:
  - Candidate anchors are searched inside the assigned deployment zone.
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
