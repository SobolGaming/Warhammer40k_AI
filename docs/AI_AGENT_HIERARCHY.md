# Hierarchical AI Agent Architecture

This document defines the implemented controller-facing separation between Warhammer 40,000 AI planning layers and concrete action-selection agents.

## Runtime Contract

The authoritative engine remains the only source of legality and mutation:

1. The engine emits a `DecisionRequest`.
2. Tier 0 decorates context with rules bundle ids, descriptor ids, Tier 1 plan context, Tier 2 task context, semantic candidate metadata, masks, and time budgets.
3. `AIControllerRouter` maps the decision to exactly one policy-bundle component.
4. The selected domain component ranks only legal `mask=True` candidates and returns an `action_id`.
5. The controller submits the normal `RESOLVE_DECISION` command.
6. The engine validates, mutates state, emits events, and records `DecisionRecord` telemetry.

The router is implemented in `src/warhammer40k_ai/engine/ai_controller_router.py`.
Framework-free deterministic domain rankers live in `src/warhammer40k_ai/engine/ai_domain_agents.py`.

## Layers

| Layer | Owner | Engine Surface |
| --- | --- | --- |
| Tier 0 | Rules/legality service | candidate generation, masks, descriptor provenance, semantic metadata, `time_budget_ms` |
| Tier 1 | Strategic planner | `Tier1Plan`, scoring/denial opportunities, resource posture, risk posture, unit priority tiers |
| Tier 2 | Tactical orchestrator | `Tier2TaskBundle`, per-unit tasks, `MovementIntent`, `compute_tier`, CP reserve policy |
| Tier 2.5 | Phase coordinator | `AIControllerRouter` role selection and fallback routing |
| Tier 3 | Domain rankers | `choose_action_id(request)` over legal candidates |
| Tier 4 | Replay/training service | `DecisionRecord`, replay, relabeling, reward annotation, manifest gates |

## Policy Bundle Components

The hierarchical runtime component names are:

- `strategic_planner`
- `tactical_orchestrator`
- `deployment_ranker`
- `movement_ranker`
- `shooting_ranker`
- `charge_ranker`
- `fight_ranker`
- `tool_ranker`
- `reaction_ranker`
- `dice_policy`
- `allocation_ranker`

Each component may be backed by a heuristic resolver or learned artifact through the existing policy-bundle manifest ABI. The default heuristic registry exposes framework-free resolver ids of the form `heuristic:<component>:v1`.

## Domain Ownership

- Deployment ranker: deployment zones, reserves declaration, deployment unit order, deployment placement, Scout moves.
- Tactical orchestrator: activation order outside fight, attachments, transports, objective/terrain binding, quarry/order-style target binding.
- Movement ranker: movement action choice, normal/fall-back/advance movement, embark/disembark, floor and point choices, coherency restoration.
- Shooting ranker: ranged target/profile declarations and shooting-phase target choices.
- Charge ranker: charge declaration and charge movement.
- Fight ranker: fight target/profile/allocation choices, fight-phase activation order, pile-in and consolidate movement.
- Tool ranker: generic stratagem/tool actions and immediate optional ability choices.
- Reaction ranker: Overwatch, reactive setup/target choices, Careen-style and opponent-window reactions.
- Dice policy: engine-owned dice and reroll/substitution decisions.
- Allocation ranker: damage, Precision, target-model, hazardous, and model-selection allocation choices.
- Strategic planner: battle-round or army-wide posture choices such as doctrines, vows, blessings, rituals, secondaries, and broad resource posture.

Shared decision surfaces are context-sensitive. For example, `MOVE_UNIT` routes to deployment, charge, fight, or movement depending on `placement_kind`, `phase_step`, and `movement_type`.

## Fallback Policy

Routing is deterministic:

- If the primary component returns a masked, missing, or empty action id, the router tries configured fallbacks for the same component.
- If no component produces a legal action, the router chooses the first legal action id.
- Optional and reaction fallback paths prefer deterministic decline/skip candidates when such a candidate exists.
- Components never generate legality, mutate state, inspect UI-only objects, or submit commands directly.

## Headless Integration

`HeadlessPolicyDecisionController` accepts an optional `AIControllerRouter`. When provided, the router preselects the first candidate tried by the existing headless resolver. The resolver still uses the normal command path, payload normalization, reserves-arrival safeguards, and authoritative validation.

### Headless Decision Flow

Headless mode resolves the same `DecisionRequest` objects as UI and network play. The controller can rank candidates, but legality, mutation, follow-up decisions, and telemetry stay inside the authoritative engine path.

Tier 1 and Tier 2 are currently deterministic, cached context builders rather than independent player-facing decisions. They are created at Command phase start when possible, and lazily inside `Game.request_decision(...)` for any player decision that needs strategic context.

```mermaid
flowchart TD
  A["Command phase start or first decision for player this battle round"] --> B["get_or_create_tier1_plan(player_id)"]
  B --> C["build_heuristic_tier1_plan from mission, objectives, score state, resources, and unit priorities"]
  C --> D["Cache Tier1Plan by battle_round and player_id"]
  D --> E["get_or_create_tier2_task_bundle(player_id)"]
  E --> F["build_tier2_task_bundle maps units to task_type, compute_tier, MovementIntent, and CP reserve policy"]
  F --> G["Cache Tier2TaskBundle by battle_round and player_id"]
  G --> H["Game.request_decision injects turn_plan, score_window_state, opportunity_catalog, and cp_reserve_policy"]
  H --> I{"Decision has unit_id?"}
  I -->|"Yes"| J["Inject tier2_task, movement_intent, and compute_tier for that unit"]
  I -->|"No"| K["Use global strategic context only"]
  J --> L["Candidate generators and semantic metadata consume the strategic context"]
  K --> L
  L --> M["AIControllerRouter maps the request to the Tier 3 domain ranker"]
  M --> N["Domain ranker orders legal candidates only"]
  N --> O["DecisionRecord preserves plan/task context with chosen_action_id and outcome"]
  O --> P["State mutation affects future requests; next battle-round cache rebuild reflects new state"]
```

```mermaid
flowchart TD
  A["Phase, setup, rule, or ability hook needs player input"] --> B["Build DecisionRequest with type, options, and context"]
  B --> C["Game.request_decision"]
  C --> D["Normalize limited-use context and attach rules, descriptor, plan, task, and time-budget metadata"]
  D --> E{"Decision type"}
  E -->|"Deployment/setup"| F["Generate deployment candidates and masks"]
  E -->|"MOVE_UNIT"| G["Generate movement candidates, masks, and PathWitness references"]
  E -->|"SELECT_MOVEMENT_ACTION in Movement phase"| H["Generate endpoint-aware movement-action candidates"]
  E -->|"Other"| I["Finalize option-derived candidates"]
  F --> J["Ensure semantic candidate metadata"]
  G --> J
  H --> J
  I --> J
  J --> K["Queue request and publish decision_requested"]
  K --> L{"Controller handling request"}
  L -->|"Dice or reroll request"| M["AutoDiceDecisionController resolves roll/reroll"]
  L -->|"Non-dice headless request"| N["HeadlessPolicyDecisionController ranks legal mask=true candidates"]
  N --> O{"AI router eligible?"}
  O -->|"Yes"| P["AIControllerRouter reranks legal tactical candidates"]
  O -->|"No"| Q["Use headless ranking directly"]
  P --> R["Submit first candidate that passes preflight"]
  Q --> R
  M --> S["Submit RESOLVE_DECISION command"]
  R --> S
  S --> T["Command dispatcher validates player, option id, mask, and handler legality"]
  T --> U{"Accepted?"}
  U -->|"No"| V["Record invalid DecisionRecord with invalid_attempt and rejection_reason"]
  U -->|"Yes"| W["Dispatch handler and mutate state"]
  W --> X["Record valid DecisionRecord with chosen_action_id and outcome"]
  X --> Y["Publish decision_resolved, queue rule/phase follow-ups, then publish decision_settled"]
  Y --> Z{"Pending follow-up?"}
  Z -->|"Yes"| K
  Z -->|"No"| AA["Phase/setup loop continues"]
```

Movement-phase activation has an additional audit constraint: every eligible alive battlefield unit must receive a movement activation, and `SELECT_MOVEMENT_ACTION` is derived from the movement endpoint rather than chosen independently from the final `MOVE_UNIT` payload.

```mermaid
flowchart TD
  A["Movement phase MOVE_UNITS step starts or resumes"] --> B{"Alive, battlefield, non-embarked, non-reserve units still eligible?"}
  B -->|"No"| C["Movement step can advance"]
  B -->|"Yes"| D["SELECT_UNIT chooses next eligible unit"]
  D --> E["SELECT_MOVEMENT_ACTION plans the desired endpoint first"]
  E --> F{"Least restrictive legal action for planned displacement"}
  F -->|"REMAIN_STATIONARY"| G["Apply remained-stationary movement flag"]
  F -->|"NORMAL or FALL_BACK"| H["Queue MOVE_UNIT using normal movement allowance"]
  F -->|"ADVANCE"| I["Resolve advance modifiers and REQUEST_DICE_ROLL"]
  I --> J["Queue MOVE_UNIT using movement plus advance result"]
  H --> K["MOVE_UNIT validates per-model displacement, identity, coherency, and PathWitness"]
  J --> K
  K --> L["Apply model positions and movement flags"]
  L --> M["Queue disembark/embark or other movement follow-ups when legal"]
  G --> B
  M --> B
```

Shooting-phase activation repeatedly selects eligible shooters until no eligible units remain or the controller passes, and a selected transport can first branch through Firing Deck before its own `DECLARE_SHOTS` request. Attack resolution can interleave dice, reroll, allocation, and reaction decisions before the shooter loop resumes.

```mermaid
flowchart TD
  A["Shooting phase SHOOT_UNITS step starts or resumes"] --> B{"Eligible shooting units remain?"}
  B -->|"No"| C["Shooting step can advance"]
  B -->|"Yes"| D["SELECT_UNIT chooses shooter or pass"]
  D -->|"Pass"| C
  D -->|"Shooter selected"| E{"Transport has unresolved Firing Deck request?"}
  E -->|"Yes"| F["DECLARE_FIRING_DECK selects embarked firing models/weapons"]
  F --> G["DECLARE_SHOTS for selected unit"]
  E -->|"No"| G
  G --> H["Resolve ranged declarations and attacks"]
  H --> I["REQUEST_DICE_ROLL, reroll, target-model, Precision, damage-allocation decisions as needed"]
  I --> J["Apply damage, destruction, post-shoot ability effects, and reaction windows"]
  J --> B
```

Charge-phase activation selects a charging unit, declares targets, rolls the charge, then queues the concrete `MOVE_UNIT` charge move only when the declaration and roll produce a legal move window.

```mermaid
flowchart TD
  A["Charge phase DECLARE_CHARGES step starts or resumes"] --> B{"Eligible charging units remain?"}
  B -->|"No"| C["Charge step can advance"]
  B -->|"Yes"| D["SELECT_UNIT chooses charger or pass"]
  D -->|"Pass"| C
  D -->|"Charger selected"| E["DECLARE_CHARGE chooses target unit ids or skips"]
  E --> F{"Any declared charge targets?"}
  F -->|"No"| B
  F -->|"Yes"| G["Resolve charge modifiers and REQUEST_DICE_ROLL"]
  G --> H["SELECT_DICE_REROLL or other dice policy decisions as needed"]
  H --> I{"Charge roll reaches a legal target?"}
  I -->|"No"| B
  I -->|"Yes"| J["MOVE_UNIT with movement_type=charge and target_unit_ids"]
  J --> K["Validate charge path, engagement, coherency, and PathWitness"]
  K --> L["Apply charge movement, charged flag, charge-end effects, and reaction windows"]
  L --> B
```

Fight-phase activation is stage-based rather than active-player-only. The `FightPhaseManager` runs Fight First, then Remaining Combatants, and may add a consolidate batch stage for units that still need a consolidate move.

```mermaid
flowchart TD
  A["Fight phase starts"] --> B["FightPhaseManager starts Fight First stage"]
  B --> C{"Current stage has eligible fighters?"}
  C -->|"No"| D{"More fight stages?"}
  D -->|"Yes"| E["Advance to next stage: Remaining Combatants or Consolidate Batch"]
  E --> C
  D -->|"No"| F["Fight phase complete"]
  C -->|"Yes"| G["SELECT_UNIT chooses next fighting unit for active fight player"]
  G --> H["Publish fight_unit_selected reaction window"]
  H --> I{"Eligible melee targets after any required pre-target choice?"}
  I -->|"No, overrun available"| J["MOVE_UNIT pile_in to regain engagement"]
  J --> I
  I -->|"No"| K["Mark unit handled and switch active fight player"]
  K --> C
  I -->|"Yes"| L["SELECT_FIGHT_TARGETS chooses one or all engaged targets"]
  L --> M["Publish fight_targets_selected reaction window"]
  M --> N["MOVE_UNIT pile_in"]
  N --> O["Optional fight-within-3 or other ability confirmations"]
  O --> P["DECLARE_MELEE_WEAPONS"]
  P --> Q{"Multiple target units?"}
  Q -->|"Yes"| R["ALLOCATE_MELEE_TARGETS"]
  Q -->|"No"| S["Resolve melee attacks"]
  R --> S
  S --> T["REQUEST_DICE_ROLL, reroll, Precision, target-model, and damage-allocation decisions as needed"]
  T --> U["Apply damage and post-fight effects"]
  U --> V["MOVE_UNIT consolidate"]
  V --> W["Mark fought, publish fight_sequence_complete, switch active fight player"]
  W --> C
```

Stratagem and other tool-action windows are not a separate phase. They are evaluated at phase hooks and after authoritative commands settle, including opponent-window reactions such as movement, charge, target-selection, or destruction triggers.

```mermaid
flowchart TD
  A["Phase hook or authoritative event occurs"] --> B["Stratagem managers update available items and pending reaction payloads"]
  B --> C["Base command or decision resolves through authoritative engine"]
  C --> D{"Decision queue empty after follow-ups?"}
  D -->|"No"| E["Resolve pending base/follow-up decision first"]
  E --> C
  D -->|"Yes"| F["Post-command tool scan"]
  F --> G["Ask non-current players, then current player, for reactions_only tool actions"]
  G --> H{"Any legal reaction candidate?"}
  H -->|"Yes"| I["SELECT_TOOL_ACTION with reaction context and skip option"]
  H -->|"No"| J["Ask current player, then other players, for normal phase tool actions"]
  J --> K{"Any legal normal tool candidate?"}
  K -->|"Yes"| L["SELECT_TOOL_ACTION with phase context and skip option"]
  K -->|"No"| M["Resume base phase flow"]
  I --> N["Validate timing, CP, limited-use key, required bindings, and target legality"]
  L --> N
  N --> O{"Use or skip?"}
  O -->|"Skip"| P["Mark signature skipped for this window"]
  O -->|"Use"| Q["manager.use applies stratagem, consumes resources, dequeues reaction, and queues follow-ups"]
  P --> M
  Q --> C
```

Audit checklist:
- Review `decision_requested` event order, then the matching `DecisionRecord` order.
- For each record, verify `request_context.phase_name`, `phase_step`, `selection_purpose`, `ability`, and limited-use metadata before interpreting the choice.
- For ranking audits, compare only legal `mask=true` candidates and confirm `chosen_action_id` appears in `candidates`.
- For movement audits, inspect `SELECT_MOVEMENT_ACTION` candidate metadata and the following `MOVE_UNIT` payload together; an `ADVANCE` label is invalid when the chosen model positions were reachable by a Normal Move unless a rule explicitly forces that state.
- For shooting audits, inspect `DECLARE_FIRING_DECK` before the transport's `DECLARE_SHOTS`, then follow any dice/allocation records produced by the ranged attack sequence.
- For charge audits, inspect `DECLARE_CHARGE`, charge dice/reroll records, and the following charge `MOVE_UNIT` as one sequence.
- For fight audits, inspect the stage-bearing `SELECT_UNIT`, `SELECT_FIGHT_TARGETS`, pile-in `MOVE_UNIT`, melee declaration/allocation records, melee attack resolution records, and consolidate `MOVE_UNIT` together.
- For stratagem audits, inspect `SELECT_TOOL_ACTION` context fields such as `reactions_only`, `tool_action_signature`, `phase_name`, `limited_use_*`, and the triggering event context before judging Use versus Skip.
- For strategic-flow audits, inspect `plan_id`, `turn_plan`, `score_window_state`, `opportunity_catalog`, `cp_reserve_policy`, `tier2_task`, `movement_intent`, and `compute_tier` inside `request_context`; these explain why lower-layer candidates were generated or scored the way they were.
- If the engine changes decision ordering, update these diagrams and the affected decision/replay docs in the same change.

LLM-backed domain agents are documented in `docs/LLM_AGENT_RUNTIME.md`. They implement the same component contract and fall back to the deterministic rankers described here when the provider is unavailable or returns an illegal action id.

## Human Training Mode

`scripts/run_training_mode.py` provides one-step human imitation drills for this same component/action-id
hierarchy. The first implemented stages are `shooting_phase` (`DECLARE_SHOTS` -> `shooting_ranker`) and
`deployment_reserves` (`DECLARE_RESERVES` -> `deployment_ranker`). The Pygame training UI shows a generated
situation, asks the user to choose one legal candidate, evaluates that single decision, writes a JSONL
observation, and updates a framework-free preference model.

These observations are scoped training records rather than full-game `DecisionRecord`s. They preserve the
serialized `DecisionRequest`, candidate masks, chosen action id, component name, reward, and supervised-example
payload so later LLM or learned ranker pipelines can consume human selections without changing the authoritative
engine boundary. See `docs/TRAINING_MODE.md`.
