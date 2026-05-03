# Deployment Architecture

## Overview
The deployment system follows the current Chapter Approved setup sequence and supports both UI-driven
manual placement and controller-driven automation.

Key goals:
- One deployment pipeline for all controllers
- Mission-aware deployment zones (polygons + cutouts)
- Deterministic deployment order with the TITANIC skip-turn rule

## Core components
- `DeploymentManager` in `src/warhammer40k_ai/engine/deployment.py` runs the official sequence.
- `DeploymentDecisionMaker` defines `choose_deployment_zone`, `declare_reserves`, and
  `choose_next_deploy_unit` / `choose_unit_deployment_position`.
- Strategic pregame choices are explicit decisions routed through the engine stack:
  `CHOOSE_DEPLOYMENT_ZONE`, `DECLARE_RESERVES`, `SELECT_NEXT_DEPLOY_UNIT`, and deployment
  placement via `MOVE_UNIT` with `placement_kind="deployment"`.
- Deployment candidate generation mirrors movement architecture:
  `src/warhammer40k_ai/engine/deployment_intent.py` and
  `src/warhammer40k_ai/engine/deployment_solver.py` produce deterministic candidates with
  semantic metadata and time-budget fallback support.
- Board affordance extraction now uses all terrain classes (not RUINS-only), with deterministic
  lane/route sampling to derive LOS tunnel pressure, hidden staging cell counts, exposure pressure,
  and objective approach quality signals for both infantry and vehicle posture.
- `DeploymentDecisionMaker` can optionally select by queued request option id
  (`choose_deployment_zone_option` / `choose_reserves_allocation_option` /
  `choose_next_deploy_unit_option` / `choose_deployment_move_option`) so learned rankers
  can consume engine-generated candidate metadata directly.
- `DECLARE_RESERVES` requests now expose deterministic multi-option allocation plans (not a single confirm-only option).
- `SCOUT_MOVE` requests now expose deterministic destination options plus skip, with deployment-semantic metadata and exact generated `model_positions` for headless application.
- Deployment `MOVE_UNIT` placement now exposes deterministic multi-candidate exact-placement options at runtime
  (`placement_candidate_id`, anchor, exact `model_positions`) instead of a single confirm-only payload.
- Deployment candidate generation now supports an optional bounded pregame lookahead layer
  (`context.deployment_lookahead`) that evaluates deterministic enemy-response branches and follow-up value.
- `HumanDeploymentDecisionMaker` delegates to `src/warhammer40k_ai/UI/human_interface.py`
  (or console fallback if no UI is available).

## Manual UI flow
- `Game.execute_deploy_armies_phase` with `manual_phases=True` sets up deployment state and defers
  placement to the UI.
- `DeploymentPhaseHandler` in `src/warhammer40k_ai/UI/phases/phase_manager.py` routes clicks to
  per-model deployment.
- `IndividualModelMovementDialog` handles per-model placement and validation.
- `Game.advance_deployment_turn` enforces alternating deployment and the TITANIC skip-turn rule.
- `Game.record_deployment_action` feeds the info pane with the last action per player.

## Deployment validation
- Zones are mission polygons stored under `game.deployment_zones[player_name]["mission_zones"]`.
- `Game.is_valid_deployment_position` enforces:
  - normal units wholly within their zone,
  - Infiltrate restrictions vs enemy zone and 9" buffer,
  - datasheet deployment special rules (e.g. Convergence Of Dominion and Aegis Defence Line section legality),
  - RUINS placement rules for per-model deployment.
- `Game.get_boundary_repulsors(context="deployment")` keeps model placement inside zone boundaries
  during formation placement.
- Speculative deployment probes snapshot and restore unit model state, so headless candidate generation
  and legality checks do not leak temporary placements into later deployment decisions.
- For larger headless unit placements, the deterministic controller first probes a coarse grid payload
  through the same fast and full deployment validators before falling back to the full prospective
  formation search. This keeps generated-army deployment deterministic while avoiding repeated
  geometry relaxation stalls when a simple legal pack is available.
- Deployment candidates include semantic deltas used by replay/telemetry and headless ranking,
  including reserve-denial, screen-integrity, countercharge-coverage, aura-connectivity, and
  enemy-first-turn exposure estimates.
- Deployment-placement candidates include per-option spatial metadata (`forward_progress_norm`,
  `lateral_offset_norm`, `anchor_center_distance_norm`) so exact placement is rankable online.
- When lookahead is enabled, deployment candidates include rollout metadata
  (`lookahead_immediate_value`, `lookahead_worst_branch_value`, `lookahead_followup_value`,
  `lookahead_enemy_pressure`, `lookahead_total_value`) plus adjusted round/trade projections.
- Zone candidates also carry board-affordance semantics (`los_tunnel_count`,
  `hidden_staging_cell_count`, `must_expose_to_advance_cell_count`,
  `infantry_objective_approach_quality`, `vehicle_objective_approach_quality`) so deployment-zone
  ranking can reason over geometry-derived staging quality.

Compound fortification section geometry and footprint resolution are documented in
`docs/MODEL_GEOMETRY_OVERRIDES.md`.

## File locations
- `src/warhammer40k_ai/engine/deployment.py`
- `src/warhammer40k_ai/engine/game.py`
- `src/warhammer40k_ai/engine/missions.py`
- `src/warhammer40k_ai/UI/human_interface.py`
- `src/warhammer40k_ai/UI/phases/phase_manager.py`
- `src/warhammer40k_ai/UI/dialogs/individual_model_movement_dialog.py`
- `src/warhammer40k_ai/UI/rendering/board_renderer.py`
