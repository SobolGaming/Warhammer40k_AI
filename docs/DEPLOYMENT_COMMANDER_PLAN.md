# Deployment Commander Plan

`DeploymentPlan` is the setup/deployment orchestration scaffold between the
game-level `GeneralPlan` and battle-round `BattleRoundPlan`.

The deployment commander is not a legality source. It does not create
deployment candidates, mask candidates, validate placements, or mutate game
state. It exposes deterministic planning context so future deployment rankers
can order already-legal candidates against higher-level deployment intent.

## Runtime Contract

- `Game.get_or_create_deployment_plan(player_id)` returns a cached plan for the
  setup/deployment stage.
- `Game.get_deployment_dirty_flags(player_id)` returns current deployment repair
  pressure.
- `Game.mark_deployment_plan_dirty(...)` records variance such as revealed enemy
  drops or reserve declarations.
- `Game.repair_deployment_plan(player_id, scope=...)` refreshes the cached
  deployment plan and consumes matching dirty flags.
- Deployment-related decision contexts receive by default:
  - `deployment_plan_id`
  - `deployment_dirty_flags`
  - `deployment_replan_scope`
  - `unit_deployment_task` for unit-scoped deployment decisions
  - `deployment_tempo_capability` for unit-scoped Scout/Infiltrate tempo
    metadata when present
  - `scout_projection` / `infiltrate_projection` for matching forward
    deployment units when present
  - `transport_deployment_task` for transports and planned passengers
- The full `deployment_plan` payload is audit/debug-only. It is attached only
  when `request.context["include_full_deployment_plan"]` or
  `game.attach_full_deployment_plan_context` is true.
- Caller-provided `deployment_plan` payloads are stripped unless that same
  audit/debug opt-in is active.

Deployment context is attached only for setup/deployment decisions, including
deployment zone choice, reserve declaration, next-unit selection, Scout moves,
and `MOVE_UNIT` requests with `placement_kind="deployment"`.

## Plan Shape

Top-level fields:

- `plan_id`
- `player_id`
- `created_at_generation`
- `mission_id`
- `deployment_map_id`
- `terrain_layout_id`
- `first_turn_unknown`
- `secondary_mode`
- `information_state`
- `doctrine`
- `unit_tasks`
- `tempo_capabilities`
- `scout_projections`
- `infiltrate_projections`
- `transport_tasks`
- `contingency_branches`
- `dirty_flags`
- `repair_count`
- `metadata`

`metadata.general_plan_id` links the deployment plan to the active
game-level General plan. General transport doctrine is consumed as planning
metadata only.

## Information State

`DeploymentInformationState` records known setup information:

- own/enemy deployed unit ids
- own/enemy unplaced unit ids
- own/enemy reserve unit ids
- own/enemy embarked unit ids
- known enemy attachment relationships
- known enemy Scout / Infiltrate capable unit ids
- unplaced own Scout / Infiltrate capable unit ids
- contested forward regions
- Scout lane metadata
- Infiltrate deny-zone metadata
- compact terrain/objective counts

This is uncertainty-aware. The plan records known mission, map, terrain,
objective, enemy-list, reserve, embarkation, and fixed-secondary state where
available, while treating first turn, unrevealed enemy drops, and tactical
secondary draws as uncertain.

## Unit Tasks

`UnitDeploymentTask` exposes unit-local deployment posture:

- `role`: `hide`, `screen`, `stage`, `alpha`, `score`, `counterpunch`,
  `reserve`, or `transported`
- `preferred_regions`
- `forbidden_regions`
- `needs_obscuring`
- `avoid_alpha_exposure`
- `preserve_for_late_game`
- `supports_transport_plan`
- `go_first_value`
- `go_second_safety`
- `tactical_flexibility`
- `deployment_sequence_priority`
- `preferred_drop_window`
- `has_scout`
- `has_infiltrate`
- `scout_lane_targets`
- `infiltrate_screen_regions`
- `counter_scout_regions`
- `no_mans_land_pressure_regions`

The initial scaffold uses conservative heuristics:

- high-value shooting units hide behind obscuring when first turn is unknown.
- Scout/infiltration/screen units receive forward screen and reserve-denial
  posture, plus early-drop tempo metadata.
- reserve units receive reserve-pool and late-game preservation posture.
- embarked or planned passenger units receive transported posture.
- transports receive staging posture plus a transport deployment task.

## Deployment Tempo

PR7B models Scout and Infiltrate as deployment-order-sensitive capabilities.
The scaffold does not choose a unit or placement yet; it exposes deterministic
metadata for PR8 ranking.

`DeploymentTempoCapability` records:

- `has_scout`
- `has_infiltrate`
- `scout_distance_inches`
- `forward_deploy_distance_class`
- `blocks_enemy_scout_lanes`
- `screens_enemy_infiltrate`
- `early_drop_priority`
- `late_drop_priority`
- `reveal_risk`

Scout units also receive a `ScoutProjection` with:

- forward deployment-zone edge region
- projected post-Scout cover regions
- lane screening ids
- objective pressure ids
- go-first value, go-second value, and go-second exposure

Infiltrate units receive an `InfiltrateProjection` with:

- forward counter-Scout screen region
- blocked enemy Scout lanes
- screened objectives
- denied enemy forward regions
- preserved own Scout lanes
- counter-deploy value and go-second exposure

The information state tracks enemy Scout and Infiltrate capabilities so
remaining own drops can react after enemy reveals. Enemy Scout pressure raises
own Infiltrate counter-Scout priority; enemy Infiltrate pressure marks Scout
lanes as blocked and reduces Scout early-drop value.

## Transport Tasks

`TransportDeploymentTask` bridges General transport doctrine into setup context:

- `transport_unit_id`
- `passenger_unit_ids`
- `initial_deployment_role`
- `delivery_round`
- `delivery_region_ids`
- `preserve_passengers`
- `post_delivery_role`

These tasks do not alter embark/disembark legality. They are local slices for
future deployment ranking and audit.

## Dirty Flags

`DeploymentDirtyFlags` are cumulative repair hints:

- `remaining_drops_dirty`
- `enemy_information_dirty`
- `transport_plan_dirty`
- `reserve_plan_dirty`
- `full_replan_required`
- `reasons`
- `max_severity`

Derived fields:

- `status`: `on_plan`, `minor_variance`, or `major_variance`
- `recommended_replan_scope`: `none`, `remaining_drops`, `transport_only`,
  `reserves_only`, or `full_deployment`

The scaffold subscribes to deployment reveal events:

- `unit_deployed` / `deployment_unit_deployed`: dirty remaining own drops, and
  dirty enemy information when the deployed unit belongs to the opponent.
- `enemy_scout_deployed` and `enemy_infiltrate_deployed`: dirty remaining own
  drops and enemy information with higher tempo variance severity.
- `deployment_region_contested` and `scout_lane_blocked`: dirty remaining own
  drops when forward space or Scout lanes are contested.
- `deployment_reserves_declared`: dirty reserve planning and enemy information
  for opposing declarations.

## Current Baseline

PR7 is deliberately non-behavioral:

- no deployment candidate generation changes.
- no deployment masks change.
- no placement validation changes.
- no deployment ranker consumes these fields yet.
- full plan payload remains audit/debug-only.

PR8 is expected to make the deployment ranker consume these local slices when
ordering legal deployment candidates.
