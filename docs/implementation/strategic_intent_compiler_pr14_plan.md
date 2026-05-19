# PR14 — Strategic Intent Compiler: General → Deployment → Pre-Battle → Battle-Round Orders

## Goal

Implement an explicit compiler layer that translates high-level `GeneralPlan` intent into three lower-order planning products:

```text
GeneralPlan
  ↓ compile
DeploymentOrderBundle
  ↓ materialize
DeploymentPlan

GeneralPlan + DeploymentPlan
  ↓ compile
PreBattleOrderBundle
  ↓ materialize
Scout / Infiltrate / pre-battle movement directives

GeneralPlan + DeploymentPlan + current board state
  ↓ compile
CommanderOrderBundle
  ↓ materialize
BattleRoundPlan
```

This PR should make strategic intent traceable from whole-game General policy down to deployment order, Scout/Infiltrate pre-battle movement, and battle-round movement/shooting/charge/fight orders.

The compiler should remain non-authoritative for legality. It may create planning metadata and preferred-order bundles, but the existing engine, validators, masks, deployment solver, movement validator, shooting validator, charge/fight validators, and PathWitness artifacts remain authoritative.

---

## Current assumed architecture after PR13

The repo now treats the orchestration stack as:

```text
GeneralPlan
DeploymentPlan
BattleRoundPlan
phase rankers
engine legality / mutation authority
```

The General owns whole-game strategy, scarce resources, once-per-game timing, CP policy, transport doctrine, late-game preservation, and battle-round posture. The Deployment Commander owns setup/deployment under uncertainty. The Battle-Round Commander owns per-round movement/shooting/charge/fight orchestration and repair. Rankers only order legal candidates. Engine validation remains authoritative.

The roadmap already includes completed DeploymentPlan / DeploymentCommander scaffold, deployment tempo scaffold for Scout/Infiltrate, and deployment ranker consumption of deployment commander intent.

PR14 should connect these layers through a formal intent compiler.

---

## Non-goals

Do **not**:

```text
- create legal deployment candidates
- create legal movement candidates
- create legal shooting declarations
- alter masks
- bypass validation
- mutate game state
- replace existing deployment/movement/shooting/charge/fight solvers
- attach full compiled bundles to normal decision context
```

Compiled orders are planning metadata and scoring inputs only.

---

## New module

Create:

```text
src/warhammer40k_ai/engine/strategic_intent_compiler.py
```

This module owns translation from `GeneralPlan` into:

```text
DeploymentOrderBundle
PreBattleOrderBundle
CommanderOrderBundle
```

Keep this module side-effect free and deterministic.

---

## New data model

Use frozen dataclasses with deterministic `to_dict()` methods.

All dictionaries must sort by key. All lists that are not intentionally ordered must be sorted. Lists representing priority order must be preserved and include deterministic tie-breakers.

---

# 1. General-level compiled directive

## `RoundCommanderDirective`

```python
@dataclass(frozen=True)
class RoundCommanderDirective:
    directive_id: str
    player_id: str
    battle_round: int
    posture: str  # "stage", "push", "preserve"

    aggression_budget: float
    exposure_budget: float
    trade_budget: float
    resource_budget: float
    cp_reserve_target: float

    preserve_unit_ids: list[str] = field(default_factory=list)
    primary_phase_focus: str = ""  # "deployment", "movement", "shooting", "charge", "fight", "score"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## Posture budget defaults

Use deterministic defaults when a General directive is missing:

```python
POSTURE_BUDGETS = {
    "stage": {
        "aggression_budget": 0.25,
        "exposure_budget": 0.25,
        "trade_budget": 0.20,
        "resource_budget": 0.20,
        "primary_phase_focus": "movement",
    },
    "push": {
        "aggression_budget": 0.75,
        "exposure_budget": 0.55,
        "trade_budget": 0.70,
        "resource_budget": 0.70,
        "primary_phase_focus": "shooting",
    },
    "preserve": {
        "aggression_budget": 0.20,
        "exposure_budget": 0.15,
        "trade_budget": 0.10,
        "resource_budget": 0.10,
        "primary_phase_focus": "score",
    },
}
```

Default round posture:

```text
Round 1: stage
Rounds 2-3: push
Rounds 4-5: preserve
```

---

# 2. Deployment intent model

Deployment requires a separate compiled order bundle because deployment happens under structured uncertainty:

```text
known:
- primary mission
- deployment map
- terrain layout
- objectives
- own list
- enemy list
- enemy attachments
- reserves
- embarkation / transport state
- fixed secondaries if fixed

unknown:
- first turn
- exact enemy deployment locations for unplaced units
- enemy alternating-drop choices
- tactical secondary draws
```

## `DeploymentOrderBundle`

```python
@dataclass(frozen=True)
class DeploymentOrderBundle:
    order_bundle_id: str
    player_id: str
    general_plan_id: str
    deployment_plan_id: str | None = None

    doctrine: DeploymentDoctrineOrder
    information_state: DeploymentInformationOrder

    unit_orders: dict[str, DeploymentUnitOrder] = field(default_factory=dict)
    transport_orders: dict[str, DeploymentTransportOrder] = field(default_factory=dict)
    sequence_orders: dict[str, DeploymentSequenceOrder] = field(default_factory=dict)
    contingency_branches: list[DeploymentContingencyOrder] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `DeploymentDoctrineOrder`

```python
@dataclass(frozen=True)
class DeploymentDoctrineOrder:
    first_turn_unknown: bool = True
    secondary_mode: str = "unknown"  # "fixed", "tactical", "unknown"

    go_first_posture: str = "stage"
    go_second_posture: str = "hide_counterpunch"

    tactical_flexibility_weight: float = 0.5
    fixed_secondary_specificity_weight: float = 0.5

    alpha_exposure_risk_weight: float = 1.0
    preserve_high_value_units: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `DeploymentInformationOrder`

```python
@dataclass(frozen=True)
class DeploymentInformationOrder:
    own_deployed_unit_ids: list[str] = field(default_factory=list)
    enemy_deployed_unit_ids: list[str] = field(default_factory=list)
    own_unplaced_unit_ids: list[str] = field(default_factory=list)
    enemy_unplaced_unit_ids: list[str] = field(default_factory=list)

    own_reserve_unit_ids: list[str] = field(default_factory=list)
    enemy_reserve_unit_ids: list[str] = field(default_factory=list)

    own_embarked_unit_ids: list[str] = field(default_factory=list)
    enemy_embarked_unit_ids: list[str] = field(default_factory=list)

    known_enemy_attachment_unit_ids: list[str] = field(default_factory=list)
    known_enemy_transport_unit_ids: list[str] = field(default_factory=list)

    enemy_scout_unit_ids_known: list[str] = field(default_factory=list)
    enemy_infiltrate_unit_ids_known: list[str] = field(default_factory=list)
    own_scout_unit_ids_unplaced: list[str] = field(default_factory=list)
    own_infiltrate_unit_ids_unplaced: list[str] = field(default_factory=list)

    contested_forward_region_ids: list[str] = field(default_factory=list)
    blocked_scout_lane_ids: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `DeploymentUnitOrder`

```python
@dataclass(frozen=True)
class DeploymentUnitOrder:
    unit_id: str
    role: str  # "hide", "screen", "stage", "alpha", "score", "counterpunch", "reserve", "transported"

    preferred_region_ids: list[str] = field(default_factory=list)
    forbidden_region_ids: list[str] = field(default_factory=list)

    needs_obscuring: bool = False
    avoid_alpha_exposure: bool = True
    preserve_for_late_game: bool = False
    supports_transport_plan: bool = False

    go_first_value: float = 0.0
    go_second_safety: float = 0.0
    tactical_flexibility: float = 0.0

    deployment_sequence_priority: float = 0.0
    preferred_drop_window: str = "any"  # "early", "middle", "late", "any"

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `DeploymentTransportOrder`

```python
@dataclass(frozen=True)
class DeploymentTransportOrder:
    transport_unit_id: str
    passenger_unit_ids: list[str] = field(default_factory=list)

    initial_deployment_role: str = "hidden_delivery"  # "hidden_delivery", "midboard_pressure", "screen", "reserve_delivery"
    delivery_round: int | None = None
    delivery_region_ids: list[str] = field(default_factory=list)

    preserve_passengers: bool = True
    post_delivery_role: str = "screen_objective"

    preferred_region_ids: list[str] = field(default_factory=list)
    needs_obscuring: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `DeploymentSequenceOrder`

```python
@dataclass(frozen=True)
class DeploymentSequenceOrder:
    unit_id: str
    preferred_drop_window: str = "any"  # "early", "middle", "late"
    sequence_priority: float = 0.0
    reveal_risk: float = 0.0
    counter_deploy_value: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

---

# 3. Scout and Infiltrate deployment-tempo model

Scout and Infiltrate must be treated as deployment-order-sensitive capabilities.

They should affect both:

```text
1. which unit to deploy next
2. where to deploy that unit
3. what pre-battle movement order is planned
```

## `DeploymentTempoOrder`

```python
@dataclass(frozen=True)
class DeploymentTempoOrder:
    unit_id: str

    has_scout: bool = False
    scout_distance_inches: float = 0.0
    has_infiltrate: bool = False

    early_drop_priority: float = 0.0
    late_drop_priority: float = 0.0
    reveal_risk: float = 0.0

    scout_lane_target_ids: list[str] = field(default_factory=list)
    no_mans_land_pressure_region_ids: list[str] = field(default_factory=list)
    counter_scout_region_ids: list[str] = field(default_factory=list)
    infiltrate_screen_region_ids: list[str] = field(default_factory=list)
    enemy_forward_deny_region_ids: list[str] = field(default_factory=list)

    blocks_enemy_scout_lanes: bool = False
    screens_enemy_infiltrate: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `ScoutProjectionOrder`

```python
@dataclass(frozen=True)
class ScoutProjectionOrder:
    unit_id: str
    deployment_region_id: str

    scout_distance_inches: float
    projected_region_ids_after_scout: list[str] = field(default_factory=list)

    can_reach_cover: bool = False
    can_threaten_objective_ids: list[str] = field(default_factory=list)
    can_screen_lane_ids: list[str] = field(default_factory=list)

    value_if_go_first: float = 0.0
    value_if_go_second: float = 0.0
    exposure_if_go_second: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `InfiltrateProjectionOrder`

```python
@dataclass(frozen=True)
class InfiltrateProjectionOrder:
    unit_id: str
    infiltrate_region_id: str

    blocks_enemy_scout_lane_ids: list[str] = field(default_factory=list)
    screens_objective_ids: list[str] = field(default_factory=list)
    denies_enemy_forward_region_ids: list[str] = field(default_factory=list)
    preserves_own_scout_lane_ids: list[str] = field(default_factory=list)

    counter_deploy_value: float = 0.0
    exposure_if_go_second: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

---

# 4. Pre-battle order model

Pre-battle orders are not normal Movement phase orders. They should sit between Deployment and Battle Round 1.

## `PreBattleOrderBundle`

```python
@dataclass(frozen=True)
class PreBattleOrderBundle:
    order_bundle_id: str
    player_id: str
    general_plan_id: str
    deployment_order_bundle_id: str

    scout_orders: dict[str, ScoutMoveOrder] = field(default_factory=dict)
    infiltrate_orders: dict[str, InfiltrateDeploymentOrder] = field(default_factory=dict)
    prebattle_screen_orders: dict[str, PreBattleScreenOrder] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `ScoutMoveOrder`

```python
@dataclass(frozen=True)
class ScoutMoveOrder:
    unit_id: str

    scout_distance_inches: float
    intent: str  # "move_to_cover", "threaten_objective", "screen_lane", "preserve", "counter_screen"

    destination_region_ids: list[str] = field(default_factory=list)
    objective_threat_ids: list[str] = field(default_factory=list)
    cover_region_ids: list[str] = field(default_factory=list)
    lane_screen_ids: list[str] = field(default_factory=list)

    avoid_exposure_if_go_second: bool = True
    priority: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `InfiltrateDeploymentOrder`

```python
@dataclass(frozen=True)
class InfiltrateDeploymentOrder:
    unit_id: str

    intent: str  # "forward_screen", "counter_scout", "objective_screen", "deny_forward_space"
    infiltrate_region_ids: list[str] = field(default_factory=list)

    blocks_enemy_scout_lane_ids: list[str] = field(default_factory=list)
    denies_enemy_forward_region_ids: list[str] = field(default_factory=list)
    screens_objective_ids: list[str] = field(default_factory=list)

    avoid_exposure_if_go_second: bool = True
    priority: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

## `PreBattleScreenOrder`

```python
@dataclass(frozen=True)
class PreBattleScreenOrder:
    unit_id: str
    screen_region_ids: list[str] = field(default_factory=list)
    protects_unit_ids: list[str] = field(default_factory=list)
    denies_enemy_region_ids: list[str] = field(default_factory=list)
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

---

# 5. Battle-round commander order model

Use the earlier `CommanderOrderBundle`, but include links to deployment and pre-battle results.

## `CommanderOrderBundle`

```python
@dataclass(frozen=True)
class CommanderOrderBundle:
    order_bundle_id: str
    player_id: str
    battle_round: int

    general_plan_id: str
    deployment_order_bundle_id: str | None = None
    prebattle_order_bundle_id: str | None = None

    directive: RoundCommanderDirective
    constraints: CommanderConstraintSet

    target_orders: dict[str, TargetOrder] = field(default_factory=dict)
    unit_orders: dict[str, UnitOrder] = field(default_factory=dict)
    resource_authorizations: dict[str, ResourceAuthorization] = field(default_factory=dict)
    transport_orders: dict[str, TransportRoundOrder] = field(default_factory=dict)
    phase_priorities: dict[str, float] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
```

Keep `TargetOrder`, `UnitOrder`, `MovementOrder`, `ShootingOrder`, `ChargeOrder`, `FightOrder`, `ResourceAuthorization`, and `TransportRoundOrder` from the previous plan.

Add deployment/pre-battle provenance to all relevant order metadata:

```python
metadata = {
    "general_plan_id": ...,
    "deployment_order_bundle_id": ...,
    "prebattle_order_bundle_id": ...,
    "commander_order_bundle_id": ...,
    "source_intent_kinds": [...],
}
```

---

# Compiler entry points

Implement these functions.

## `compile_general_intent_to_deployment_orders`

```python
def compile_general_intent_to_deployment_orders(
    game: object,
    general_plan: GeneralPlan,
    *,
    player_id: str,
) -> DeploymentOrderBundle:
    ...
```

## `compile_deployment_to_prebattle_orders`

```python
def compile_deployment_to_prebattle_orders(
    game: object,
    general_plan: GeneralPlan,
    deployment_orders: DeploymentOrderBundle,
    *,
    player_id: str,
) -> PreBattleOrderBundle:
    ...
```

## `compile_general_intent_to_commander_orders`

```python
def compile_general_intent_to_commander_orders(
    game: object,
    general_plan: GeneralPlan,
    deployment_orders: DeploymentOrderBundle | None,
    prebattle_orders: PreBattleOrderBundle | None,
    tier1_plan: Tier1Plan,
    tier2_bundle: Tier2TaskBundle,
    commander_analysis: CommanderAnalysisSnapshot,
    *,
    battle_round: int,
    player_id: str,
) -> CommanderOrderBundle:
    ...
```

All functions must be deterministic and side-effect free.

---

# Deployment compiler algorithm

## Pass D1 — Build deployment doctrine

Inputs:

```text
GeneralPlan
primary mission
deployment layout
terrain layout
secondary mode
reserve policy
transport doctrine
```

Infer:

```text
first_turn_unknown = True unless game state says otherwise
secondary_mode = fixed / tactical / unknown
go_first_posture
go_second_posture
tactical_flexibility_weight
fixed_secondary_specificity_weight
```

Rules:

```text
Fixed secondary:
  increase fixed_secondary_specificity_weight
  prefer known scoring lanes/objectives

Tactical secondary:
  increase tactical_flexibility_weight
  prefer central/multi-lane/action-capable deployment

First turn unknown:
  increase alpha_exposure_risk_weight
  protect high-value shooters
```

## Pass D2 — Build information state

Collect:

```text
own deployed / unplaced
enemy deployed / unplaced
own reserves
enemy reserves
own embarked
enemy embarked
known enemy attachments
known enemy transports
known Scout/Infiltrate units
contested forward regions
blocked Scout lanes
```

If exact enemy deployment is unknown, keep uncertainty explicit. Do not hallucinate exact enemy positions.

## Pass D3 — Classify deployment unit roles

For each own unit:

```text
transported passenger → transported
transport → transport_delivery / hidden_delivery / screen
high-value shooter → hide / alpha depending doctrine
screen unit → screen
Scout unit → scout_tempo
Infiltrate unit → infiltrate_tempo
durable melee unit → stage / counterpunch
late scoring unit → score / preserve
reserve unit → reserve
```

## Pass D4 — Compile Scout/Infiltrate tempo orders

For `SCOUT` units:

```text
preferred_drop_window = early
deployment_sequence_priority += Scout lane value
scout_lane_target_ids = lanes near No Man's Land / objectives
no_mans_land_pressure_region_ids = forward staging regions
reveal_risk = exposure if placed too aggressively
```

For `INFILTRATE` units:

```text
preferred_drop_window = early
deployment_sequence_priority += counter-Scout / screen value
counter_scout_region_ids = regions that block enemy Scout lanes
infiltrate_screen_region_ids = forward screen regions
enemy_forward_deny_region_ids = regions that deny enemy staging
```

Enemy influence:

```text
enemy Scout known:
  raise own Infiltrate counter-Scout priority

enemy Infiltrate known:
  mark Scout lanes blocked
  reduce Scout early-drop priority on blocked lanes
  prefer alternate Scout lanes

first turn unknown:
  increase reveal_risk / go-second exposure penalty for exposed forward positions
```

## Pass D5 — Compile transport deployment orders

Use General transport doctrine:

```text
transport with passenger:
  initial role = hidden_delivery or midboard_pressure depending posture
  needs_obscuring = True if first turn unknown
  delivery_round from General doctrine
  preferred regions support delivery route

passenger:
  role = transported
  preferred deployment depends on assigned transport
```

## Pass D6 — Emit DeploymentOrderBundle

Bundle metadata:

```python
{
    "source": "strategic_intent_compiler",
    "general_plan_id": general_plan.plan_id,
    "compiled_at_generation": map_generation,
}
```

---

# Pre-battle compiler algorithm

## Pass P1 — Compile Scout move orders

For each Scout deployment tempo order:

```text
If go-first value is high and exposure manageable:
  intent = threaten_objective or screen_lane

If go-second safety is more important:
  intent = move_to_cover or preserve

If enemy Infiltrate blocks planned lane:
  choose alternate lane if available
  otherwise intent = preserve / screen nearby lane
```

Scout order priority:

```python
priority = (
    1.4 * objective_threat_value
    + 1.1 * cover_after_move_value
    + 0.8 * screen_lane_value
    + 0.6 * no_mans_land_pressure
    - 1.2 * go_second_exposure
    - 0.9 * enemy_infiltrate_block_penalty
)
```

## Pass P2 — Compile Infiltrate orders

For each Infiltrate deployment tempo order:

```text
If enemy Scout pressure exists:
  intent = counter_scout

If objective screen is valuable:
  intent = objective_screen

If enemy forward staging is dangerous:
  intent = deny_forward_space

Otherwise:
  intent = forward_screen
```

Infiltrate priority:

```python
priority = (
    1.3 * forward_screen_value
    + 1.2 * enemy_scout_lane_block_value
    + 1.0 * objective_screen_value
    + 0.8 * own_scout_lane_preservation
    + 0.6 * enemy_infiltrate_counter_value
    - 1.0 * exposure_if_go_second
)
```

## Pass P3 — Emit PreBattleOrderBundle

This bundle should be attachable to pre-battle movement / Scout-related decisions as slim local slices:

```text
prebattle_order_bundle_id
scout_move_order
infiltrate_deployment_order
prebattle_screen_order
```

Full `prebattle_order_bundle` is audit/debug-only.

---

# Battle-round commander compiler algorithm

## Pass C1 — Select General round directive

Normalize posture budgets as above.

## Pass C2 — Compile constraints

From:

```text
GeneralPlan.limited_resource_policy
GeneralPlan.resource_ledger
GeneralPlan.cp_policy
GeneralPlan.reserve_policy
GeneralPlan.transport_policy
DeploymentOrderBundle
PreBattleOrderBundle
```

Create:

```text
preserve_unit_ids
forbidden_resource_ids
reserved_resource_ids
conditionally_authorized_resource_ids
cp_reserve_target
max_exposure_by_unit
transport_constraints
reserve_constraints
```

Pre-battle consequences:

```text
If Scout order advanced unit into exposed region:
  reduce risk budget or raise preserve/screen priority

If Infiltrate order created forward screen:
  update movement/charge/screening tasks

If deployment plan preserved a unit:
  mark preserve in UnitOrder
```

## Pass C3 — Compile target orders

Use commander analysis plus General target doctrine.

Intent mapping:

```text
push + high priority → kill
push + medium priority → soften
stage + high priority → soften / delay
stage + objective threat → screen / delay
preserve + high priority → delay / avoid unless safe
low priority → ignore / opportunistic
```

## Pass C4 — Compile unit orders

Use:

```text
Tier2 task
Commander analysis
General preserve policy
DeploymentOrderBundle
PreBattleOrderBundle
Transport doctrine
Round posture
Resource authorizations
```

Deployment and pre-battle effects:

```text
unit deployed hidden:
  shooting-first unit may stay stationary / move to LoS

unit deployed as screen:
  maintain screen / deny lane

Scout unit projected to objective:
  movement order can transition to score/screen

Infiltrate unit projected as forward screen:
  movement/charge order may preserve screen or fall back to cover

transport deployed for delivery:
  passenger/transport orders inherit delivery plan
```

## Pass C5 — Compile resource authorizations

For each General limited resource:

```text
forbidden → forbidden
spent → absent or spent
reserved before round → reserved
reserved this round and target threshold met → conditionally_authorized
authorized → authorized
```

Allowed targets should be based on `TargetOrder.priority`.

## Pass C6 — Emit CommanderOrderBundle

Include provenance links:

```text
general_plan_id
deployment_order_bundle_id
prebattle_order_bundle_id
commander_order_bundle_id
compiled_at_generation
source_intent_kinds
```

---

# Integration points

## DeploymentPlan integration

Modify `get_or_create_deployment_plan(...)` / deployment plan builder to call:

```python
deployment_orders = compile_general_intent_to_deployment_orders(...)
```

Materialize:

```text
DeploymentPlan.doctrine
DeploymentPlan.information_state
DeploymentPlan.unit_deployment_tasks
DeploymentPlan.transport_deployment_tasks
DeploymentPlan.contingency_branches
DeploymentPlan tempo capability/projection slices
```

Add metadata:

```python
metadata["deployment_order_bundle_id"] = deployment_orders.order_bundle_id
metadata["deployment_order_bundle"] = deployment_orders.to_dict()  # audit-only because full plan is audit-only
```

## PreBattle integration

Add cache/API:

```python
Game.get_or_create_prebattle_order_bundle(player_id)
```

or store inside DeploymentPlan metadata if no separate service is desired.

Attach local slices to relevant pre-battle decisions:

```text
prebattle_order_bundle_id
scout_move_order
infiltrate_deployment_order
prebattle_screen_order
```

Full prebattle bundle audit/debug-only.

## BattleRoundPlan integration

Modify `build_battle_round_plan(...)` to call:

```python
commander_orders = compile_general_intent_to_commander_orders(...)
```

Use `commander_orders` to populate:

```text
priority_targets
unit_tasks
movement_plan
shooting_plan
charge_plan
fight_plan
transport_assignments
target_fire_plans
resource authorization metadata
```

Add metadata:

```python
metadata["commander_order_bundle_id"] = commander_orders.order_bundle_id
metadata["commander_order_bundle"] = commander_orders.to_dict()
```

Because full `BattleRoundPlan` is audit-only in normal context, embedding the full bundle in metadata is acceptable.

## Context attachment

Normal decision context should include only slim IDs and local slices:

```text
general_plan_id
deployment_plan_id
deployment_order_bundle_id
prebattle_order_bundle_id
battle_round_plan_id
commander_order_bundle_id

unit_deployment_task
deployment_tempo_capability
scout_projection
infiltrate_projection

scout_move_order
infiltrate_deployment_order
prebattle_screen_order

unit_battle_task
commander_movement_task
commander_transport_assignment
commander_fire_assignment
commander_charge_assignment
commander_fight_assignment
commander_resource_authorizations
```

Do not attach full bundles unless audit/debug opt-in is enabled.

Add flags if needed:

```text
include_full_deployment_order_bundle
include_full_prebattle_order_bundle
include_full_commander_order_bundle
```

Game-level flags:

```text
game.attach_full_deployment_order_bundle_context
game.attach_full_prebattle_order_bundle_context
game.attach_full_commander_order_bundle_context
```

---

# Traceability requirements

Every compiled order should include metadata:

```python
{
    "general_plan_id": "...",
    "deployment_order_bundle_id": "...",
    "prebattle_order_bundle_id": "...",
    "commander_order_bundle_id": "...",
    "source_directive_id": "...",
    "source_intent_kinds": [
        "round_posture",
        "deployment_doctrine",
        "scout_tempo",
        "infiltrate_screen",
        "resource_policy",
        "transport_doctrine",
    ],
}
```

This should allow audit paths like:

```text
Why deploy Scout early?
→ DeploymentSequenceOrder preferred early drop due to Scout lane target.

Why Scout move to cover?
→ ScoutMoveOrder chose move_to_cover because first turn was unknown and exposure risk was high.

Why did BattleRoundPlan preserve that unit?
→ General directive preserve_unit_ids plus deployment exposure metadata.

Why did one-shot weapon not fire?
→ ResourceAuthorization status was reserved or forbidden.
```

---

# Tests

Create:

```text
tests/ai/test_strategic_intent_compiler.py
```

## Test 1 — General stage directive compiles conservative budgets

Setup:

```text
Round posture = stage
```

Assert:

```text
aggression_budget low
exposure_budget low
resource_budget low
primary_phase_focus == movement
```

## Test 2 — General push directive compiles aggressive budgets

Setup:

```text
Round posture = push
high-priority target exists
```

Assert:

```text
aggression_budget high
target order intent == kill
desired_kill_probability >= 0.75
```

## Test 3 — Preserve directive protects units

Setup:

```text
General preserve_unit_ids = ["unit:home"]
```

Assert:

```text
UnitOrder.role == preserve
UnitOrder.preserve is True
movement_order avoids aggressive staging
charge_order not planned_charge
```

## Test 4 — Deployment order handles first-turn uncertainty

Setup:

```text
first turn unknown
high-value shooter
```

Assert:

```text
DeploymentUnitOrder.needs_obscuring is True
avoid_alpha_exposure is True
go_second_safety > 0
preferred_drop_window is not reckless early alpha unless unit has tempo role
```

## Test 5 — Scout unit gets early tempo deployment order

Setup:

```text
own Scout unit
No Man's Land lane available
```

Assert:

```text
DeploymentTempoOrder.has_scout is True
early_drop_priority > 0
UnitDeploymentTask.preferred_drop_window == early
scout_lane_target_ids non-empty or no_mans_land_pressure_region_ids non-empty
```

## Test 6 — Scout projection creates pre-battle move order

Setup:

```text
Scout unit with projected cover/objective access
```

Assert:

```text
PreBattleOrderBundle.scout_orders includes unit
ScoutMoveOrder.intent in {"move_to_cover", "threaten_objective", "screen_lane"}
destination_region_ids or cover_region_ids populated
```

## Test 7 — Infiltrate counters enemy Scout

Setup:

```text
enemy Scout known
own Infiltrate unit unplaced
```

Assert:

```text
DeploymentTempoOrder.has_infiltrate is True
counter_scout_region_ids non-empty
InfiltrateDeploymentOrder.intent == counter_scout or forward_screen
blocks_enemy_scout_lane_ids populated when lane exists
```

## Test 8 — Enemy Infiltrate blocks Scout lane

Setup:

```text
enemy Infiltrate known in forward lane
own Scout unit
```

Assert:

```text
blocked_scout_lane_ids includes lane
Scout early_drop_priority decreases or alternate lane selected
ScoutMoveOrder does not target blocked lane
```

## Test 9 — Transport doctrine maps through deployment and commander orders

Setup:

```text
General transport doctrine with transport and passenger
```

Assert:

```text
DeploymentTransportOrder exists
PreBattleOrderBundle does not lose passenger/transport mapping
CommanderOrderBundle.transport_orders includes delivery order
BattleRoundPlan transport assignment remains consistent
```

## Test 10 — Resource authorization threshold

Setup:

```text
LimitedResourcePolicy reserved with threshold
target below threshold
target above threshold
```

Assert:

```text
below threshold → resource not in UnitOrder.resource_permissions
above threshold → resource appears in ResourceAuthorization.allowed_target_unit_ids
```

## Test 11 — Deterministic serialization

Build twice.

Assert:

```text
DeploymentOrderBundle.to_dict() equal
PreBattleOrderBundle.to_dict() equal
CommanderOrderBundle.to_dict() equal
```

## Test 12 — Normal context remains slim

Assert normal decision context does not include:

```text
deployment_order_bundle
prebattle_order_bundle
commander_order_bundle
general_plan
deployment_plan
battle_round_plan
```

Unless explicit audit/debug opt-in is set.

## Test 13 — No legality/mask mutation

Create representative deployment/movement/shooting requests.

Assert:

```text
candidate count unchanged
mask unchanged
no validation bypass
```

---

# Documentation updates

Update:

```text
docs/COMMANDER_ROADMAP.md
docs/GENERAL_PLAN.md
docs/BATTLE_ROUND_COMMANDER_PLAN.md
docs/DEPLOYMENT_PLAN.md
docs/AI_POLICY_ORCHESTRATION.md
```

Add a new doc if useful:

```text
docs/STRATEGIC_INTENT_COMPILER.md
```

Required explanation:

```text
GeneralPlan is not consumed ad hoc by lower layers.
GeneralPlan compiles into DeploymentOrderBundle, PreBattleOrderBundle, and CommanderOrderBundle.
DeploymentPlan and BattleRoundPlan materialize those bundles into existing local slices.
Rankers consume only slim local slices.
Engine remains authoritative.
Scout/Infiltrate are deployment-tempo capabilities.
Scout pre-battle movement orders are distinct from normal Movement phase orders.
```

---

# Acceptance criteria

PR14 passes when all are true:

```text
- GeneralPlan compiles into DeploymentOrderBundle.
- DeploymentOrderBundle includes doctrine, information state, unit orders, transport orders, sequence orders, contingency orders.
- Scout and Infiltrate generate explicit deployment-tempo orders.
- Scout generates explicit pre-battle ScoutMoveOrder.
- Infiltrate generates explicit forward-screen / counter-Scout orders.
- GeneralPlan compiles into CommanderOrderBundle for battle-round execution.
- CommanderOrderBundle contains directive, constraints, target orders, unit orders, resource authorizations, transport orders, and phase priorities.
- BattleRoundPlan materializes CommanderOrderBundle into existing phase plan structures.
- DeploymentPlan materializes DeploymentOrderBundle into existing deployment task structures.
- Normal decision context remains slim.
- Full compiler outputs are audit/debug-only.
- Existing legality, masks, validators, and PathWitness behavior remain authoritative.
- Tests cover stage/push/preserve mapping, deployment uncertainty, Scout, Infiltrate, pre-battle Scout movement, transport mapping, resource authorization, determinism, and slim context.
```

---

# Suggested implementation order

1. Create `strategic_intent_compiler.py`.
2. Add all dataclasses and deterministic `to_dict()` methods.
3. Implement General round directive normalization.
4. Implement deployment doctrine and information-state compilation.
5. Implement Scout/Infiltrate tempo compilation.
6. Implement pre-battle Scout/Infiltrate order compilation.
7. Implement commander constraints and resource authorization compilation.
8. Implement target order compilation.
9. Implement unit order compilation.
10. Implement transport order compilation.
11. Integrate deployment compiler into DeploymentPlan builder.
12. Integrate pre-battle compiler/cache/API.
13. Integrate commander compiler into BattleRoundPlan builder.
14. Attach slim local context slices.
15. Add tests.
16. Update docs.
17. Run focused tests:
    ```bash
    uv run python -m pytest \
      tests/ai/test_strategic_intent_compiler.py \
      tests/ai/test_commander_plan.py \
      tests/ai/test_ai_orchestration_context.py \
      tests/engine/test_game_api_surface.py
    ```
18. Run full suite:
    ```bash
    uv run python -m pytest tests/
    ```

---

# Boundary reminder

The new compiler should create this traceable chain:

```text
GeneralPlan
  ↓
DeploymentOrderBundle
  ↓
DeploymentPlan / deployment ranker local slices

DeploymentPlan
  ↓
PreBattleOrderBundle
  ↓
Scout / Infiltrate / pre-battle local slices

GeneralPlan + DeploymentPlan + PreBattleOrderBundle
  ↓
CommanderOrderBundle
  ↓
BattleRoundPlan / phase-ranker local slices

Rankers
  ↓
legal candidate ordering only

Engine
  ↓
validation and mutation
```

Do not let compiled intent become legality.
