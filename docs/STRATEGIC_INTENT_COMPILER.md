# Strategic Intent Compiler

`strategic_intent_compiler.py` is the traceability layer between the game-level
General and the lower orchestration plans. It is deterministic and
side-effect-free: it compiles intent into serializable order bundles, but it
does not generate candidates, alter masks, validate actions, produce
PathWitness artifacts, or mutate game state.

## Flow

```text
GeneralPlan
  -> DeploymentOrderBundle
  -> DeploymentPlan local deployment slices

GeneralPlan + DeploymentOrderBundle
  -> PreBattleOrderBundle
  -> Scout/Infiltrate/pre-battle local slices

GeneralPlan + DeploymentOrderBundle + PreBattleOrderBundle + commander analysis
  -> CommanderOrderBundle
  -> BattleRoundPlan local phase slices
```

`GeneralPlan` is therefore not consumed ad hoc by lower layers. The compiler
normalizes round posture, deployment doctrine, Scout/Infiltrate tempo,
transport doctrine, resource policy, and target doctrine into explicit bundles
that plans can materialize.

## Bundles

- `DeploymentOrderBundle`: doctrine, information state, unit deployment orders,
  transport orders, sequence orders, Scout/Infiltrate tempo orders, projections,
  and contingencies.
- `PreBattleOrderBundle`: Scout move orders, Infiltrate deployment orders, and
  pre-battle screen orders. Scout pre-battle movement is distinct from normal
  Movement phase orders.
- `CommanderOrderBundle`: round directive, constraints, target orders, unit
  orders, resource authorizations, transport round orders, and phase
  priorities.

Each bundle has a deterministic `to_dict()` and carries provenance ids so audits
can trace decisions back through General, Deployment, Pre-Battle, and
Commander intent.

## Context Rules

Normal decision context stays slim. It may include ids and unit-local slices:

- `deployment_order_bundle_id`
- `prebattle_order_bundle_id`
- `commander_order_bundle_id`
- `scout_move_order`
- `infiltrate_deployment_order`
- `prebattle_screen_order`
- `commander_resource_authorizations`

Full `deployment_order_bundle`, `prebattle_order_bundle`, and
`commander_order_bundle` payloads are audit/debug-only through explicit request
or game-level opt-in flags.

## Authority Boundary

Compiled intent is scoring/planning metadata only. Rankers may use local slices
to order already-legal candidates, and the engine remains authoritative for
legality, masks, validation, PathWitness generation, and mutation.
