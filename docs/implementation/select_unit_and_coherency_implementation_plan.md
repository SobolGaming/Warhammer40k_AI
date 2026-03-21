# `SELECT_UNIT` + Coherency Implementation Plan

## Objective
Introduce an authoritative `SELECT_UNIT` decision that the engine emits for all gameplay modes, with explicit support for Movement-phase substeps, and preserve `RESOLVE_COHERENCY` only for casualty-driven coherency failures rather than ordinary movement resolution.

## Problem Summary
Today, top-level unit activation is not consistently authored by the engine. In local UI flows, clicking a unit often determines which downstream decision should exist next based on the current phase. That creates parity risk for:

- Headless gameplay
- Remote/networked gameplay
- Replay/DecisionRecord consistency

Additionally, `RESOLVE_COHERENCY` should not be part of the normal post-move chain. A legal movement/placement candidate must already end in coherency. However, coherency **does** matter after casualties: when model deaths leave a unit non-coherent, the owning player must remove additional models one by one until the unit regains coherency.

## Design Goals
- One authoritative unit-selection decision for local, headless, and remote play.
- Preserve the existing bounded downstream decisions (`SELECT_MOVEMENT_ACTION`, `MOVE_UNIT`, `DECLARE_SHOTS`, etc.).
- Model Movement phase correctly as two distinct parts:
  - `MOVE_UNITS`
  - `REINFORCEMENTS`
- Keep `MOVE_UNIT` as the placement decision for reinforcements/deployment-style battlefield entry.
- Ensure every submitted `MOVE_UNIT` destination is authoritatively revalidated as a legal end state.
- Ensure ordinary movement never succeeds with a non-coherent end state.
- Use `RESOLVE_COHERENCY` only for casualty-removal remediation after a model dies and breaks unit coherency.
- Preserve deterministic candidate ordering, replay stability, and network parity.

## Non-Goals
- No changes to Warhammer rules intent for movement legality, reserves timing, or casualty removal semantics.
- No UI-owned request creation.
- No backwards-compatibility shim where UI still authors top-level activation requests.
- No broad rewrite of downstream attack allocation semantics in the first milestone.

## New Decision Kind
Add:

- `DECISION_SELECT_UNIT = "SELECT_UNIT"`

Update:

- `src/warhammer40k_ai/engine/decision_kinds.py`
- `docs/DECISION_TYPES.md`
- `docs/NETWORK_SAVELOAD_DESIGN.md`

Suggested catalog description:

- `SELECT_UNIT` — Choose the next eligible unit to act in the current phase step.

## `SELECT_UNIT` Request Contract
`SELECT_UNIT` is a phase-step-scoped activation request, not a generic freeform unit picker.

Suggested request shape:

- `decision_type`: `SELECT_UNIT`
- `prompt`: phase-step-specific prompt, e.g. `Select a unit to act in Move Units`
- `context.phase_name`
- `context.phase_step`
- `context.selection_purpose`
- `context.allow_pass`
- `context.allowed_unit_ids`
- `context.battle_round`
- `options`: one per legal unit, plus optional `pass`
- `candidates`: deterministic unit candidates with stable `action_id`
- `mask`: aligned legality mask

Suggested `selection_purpose` values:

- `ACTIVATE_MOVEMENT_UNIT`
- `ACTIVATE_REINFORCEMENT_UNIT`
- `ACTIVATE_SHOOTING_UNIT`
- `ACTIVATE_CHARGE_UNIT`
- `ACTIVATE_FIGHT_UNIT`

Chosen payload for unit activation:

```json
{
  "unit_id": "<canonical unit id>"
}
```

Optional pass payload:

```json
{
  "action": "pass"
}
```

## Movement Phase Design
The engine must distinguish the two Movement parts explicitly in `SELECT_UNIT` context.

### Move Units
Authoritative activation model:

- `SELECT_UNIT`
- downstream request depends on the selected unit's current state and legal movement options

Context:

```json
{
  "phase_name": "MOVEMENT_PHASE",
  "phase_step": "MOVE_UNITS",
  "selection_purpose": "ACTIVATE_MOVEMENT_UNIT",
  "allow_pass": true
}
```

Eligibility rules:

- Unit belongs to active player.
- Unit is either:
  - on the battlefield and eligible to act in `MOVE_UNITS`, or
  - embarked and legally eligible to disembark in `MOVE_UNITS`
- Unit is not in reserves unless the current step is `REINFORCEMENTS`.
- Unit has not already completed a movement action this step.
- Unit is otherwise legal to activate under current rules and battle-shock/ability constraints.

Apply behavior:

- If the selected unit is an embarked passenger that is legally eligible to disembark, `SELECT_UNIT(unit_id)` queues `DISEMBARK`.
- If the selected unit is an on-board unit that can choose a movement mode, `SELECT_UNIT(unit_id)` queues `SELECT_MOVEMENT_ACTION`.
- `SELECT_MOVEMENT_ACTION` for an on-board unit then queues:
  - `MOVE_UNIT`, or
  - resolves remain stationary directly, or
  - queues other movement-mode-specific follow-up as needed
- `EMBARK` is not mutually exclusive with `MOVE_UNIT`. It is an optional follow-up that may become available after a legal move ends with every model in the unit wholly within embark range of a legal friendly transport and other embark restrictions are satisfied.
- `DISEMBARK` is also not equivalent to ordinary movement activation. A unit can disembark and later remain eligible for its own movement activation if it disembarked before its transport moved and rules allow it.

Transport sequencing requirements:

- If a unit starts the Movement phase embarked, it may choose to `DISEMBARK` only if legally allowed.
- Manual disembark placement must be legal for every model:
  - wholly within the permitted disembark distance of the transport
  - not within Engagement Range of enemy models unless an overriding rule allows it
  - valid with respect to battlefield bounds, terrain, collisions, and unit coherency
- A transport that Advanced or Fell Back this turn cannot normally allow disembarkation unless an explicit rule override exists.
- If a unit disembarks before its transport has moved, the unit may remain eligible for later movement activation in the same phase.
- If a unit disembarks after its transport moved, or from a destroyed transport, it counts as having moved and is not eligible for a later `MOVE_UNIT`; charge eligibility then follows the transport/disembark rule set and any special-rule overrides.
- A unit cannot embark after disembarking in the same phase unless an explicit rule override exists.

Movement bookkeeping requirements:

- At the end of the `MOVE_UNITS` part, any unit that was eligible to move in that part but was not selected to move is treated as having `remained_stationary`.
- Exception: a unit that legally disembarked from a transport that had not yet moved, and therefore remained eligible for its own later movement activation, must **not** be marked `remained_stationary` merely because it chose not to change location after disembarking.
- That case counts as a Normal move of distance `0"` rather than `remained_stationary`.
- Likewise, if a transport makes a Normal move and a passenger unit then legally disembarks from it under an overriding rule, that passenger unit counts as having made a Normal move.
- More generally, disembark outcomes must be recorded in movement-state bookkeeping using the transport state and the disembark timing, not inferred from whether the unit's final coordinates changed.

### Reinforcements
Authoritative chain:

- `SELECT_UNIT`
- `MOVE_UNIT` with placement-style reinforcements context

Context:

```json
{
  "phase_name": "MOVEMENT_PHASE",
  "phase_step": "REINFORCEMENTS",
  "selection_purpose": "ACTIVATE_REINFORCEMENT_UNIT",
  "battle_round": 2,
  "allow_pass": true
}
```

Follow-up `MOVE_UNIT` context should encode placement semantics:

```json
{
  "placement_kind": "reserves_arrival",
  "reserve_entry_kind": "deep_strike",
  "battle_round": 2,
  "allow_skip": true,
  "unit_id": "<canonical unit id>"
}
```

`reserve_entry_kind` must distinguish at least:

- `deep_strike`
- `strategic_reserve`
- `other`

Eligibility rules:

- Unit belongs to active player.
- Unit is still off-board.
- Unit has not already arrived.
- Unit is legal to arrive in the current battle round.
- Unit is legal to arrive under its reserve method and mission restrictions.
- Unit is legal to arrive under any ability-specific timing/placement rules.

The reinforcements candidate set must be computed separately from Move Units.

## Coherency Rules Update
### Ordinary movement
`RESOLVE_COHERENCY` must **not** occur after ordinary `MOVE_UNIT`.

Correct behavior:

- Movement candidate generation should only offer legal end states.
- Movement resolution must authoritatively revalidate the submitted end state before applying it.
- That validation must include, as applicable:
  - model ownership / complete model list integrity
  - battlefield boundary legality
  - terrain / obstacle collision legality
  - RUINS / elevated-surface legality
  - no overlap with models in the same unit
  - no overlap with models in other units
  - unit coherency at the final position
  - path witness continuity for move types that require it
  - placement-kind-specific rules such as deployment and reserves-arrival constraints
- A move that ends non-coherent is invalid and cannot resolve successfully.

This applies equally to:

- normal moves
- advances
- fall backs
- reinforcements placement
- deployment-like placement flows

### Casualty-driven coherency failure
`RESOLVE_COHERENCY` remains important when model deaths leave a unit non-coherent.

Trigger rule:

- whenever a model's `die()` path removes or marks a model destroyed, the engine must check whether the surviving unit is still coherent

If not coherent:

- queue `RESOLVE_COHERENCY`
- owning player selects additional models to destroy
- resolve one model at a time
- repeat until the unit regains coherency or is destroyed

This must work after any death source, including:

- ranged attacks
- melee attacks
- mortal wounds
- hazardous failures
- other direct model-removal effects

### `RESOLVE_COHERENCY` request semantics
`RESOLVE_COHERENCY` should now mean:

- choose one model from the non-coherent unit to remove as an additional casualty

Recommended context:

- `unit_id`
- `phase_name`
- `damage_source`
- `coherency_failure_reason="post_casualty"`
- `required_until_coherent=true`

Recommended loop:

1. model dies
2. engine checks unit coherency
3. if coherent, continue normally
4. if not coherent, queue `RESOLVE_COHERENCY`
5. player selects one additional model to remove
6. engine re-checks coherency
7. repeat until coherent or unit destroyed

This preserves explicit player choice and network/headless parity.

## Authoritative Engine Changes
### 1. Add `SELECT_UNIT`
Files:

- `src/warhammer40k_ai/engine/decision_kinds.py`
- `src/warhammer40k_ai/engine/decision_handlers/unit_selection.py`
- `docs/DECISION_TYPES.md`

Handler responsibilities:

- validate selected `unit_id`
- validate `pass` semantics
- read `phase_name`, `phase_step`, and `selection_purpose`
- queue the correct downstream authoritative request

### 2. Add engine-side request builders
Primary location:

- `src/warhammer40k_ai/engine/decision_requests.py`

Suggested helpers:

- `build_select_unit_request(...)`
- `queue_select_unit_request(...)`
- `_eligible_units_for_phase_step(...)`
- `_eligible_units_for_move_units_step(...)`
- `_eligible_units_for_reinforcements_step(...)`

Responsibilities:

- gather root units only
- sort by canonical entity id
- produce deterministic options/candidates
- produce phase-step-specific prompt/context
- support explicit `pass` when legal

### 3. Integrate with phase progression
Primary location:

- `src/warhammer40k_ai/engine/game_mixins/phase_handlers_mixin.py`

Add explicit step-level orchestration for Movement phase:

- `_queue_movement_phase_move_units_selection()`
- `_queue_movement_phase_reinforcements_selection()`

Flow for `MOVE_UNITS`:

1. queue `SELECT_UNIT`
2. on selection, queue `SELECT_MOVEMENT_ACTION`
3. on resolution, if more eligible units remain, queue next `SELECT_UNIT`
4. otherwise advance to `REINFORCEMENTS`

End-of-step bookkeeping:

- when `MOVE_UNITS` closes, mark unresolved eligible on-board units as `remained_stationary`
- do **not** mark as `remained_stationary` units whose state already indicates:
  - they made a Normal move
  - they Advanced
  - they Fell Back
  - they disembarked in a way that counts as a Normal move of `0"` or from a moved transport
- preserve the distinction between:
  - `remained_stationary`
  - `moved_this_round` because of disembark timing/state

Flow for `REINFORCEMENTS`:

1. queue `SELECT_UNIT`
2. on selection, queue placement-style `MOVE_UNIT`
3. on placement resolution, if more eligible reinforcements remain, queue next `SELECT_UNIT`
4. otherwise end Movement phase

### 4. Add casualty coherency checks
Primary locations to inspect:

- model death/removal path in `src/warhammer40k_ai/units/`
- damage allocation / attack resolution paths in `src/warhammer40k_ai/engine/attack_resolution.py`
- hazardous / mortal wound / other direct damage paths

Required behavior:

- centralize a post-death coherency check hook
- avoid duplicating coherency-remediation logic in every damage source
- queue `RESOLVE_COHERENCY` from the authoritative game layer

Preferred pattern:

- model death path raises or emits a single authoritative follow-up hook
- that hook resolves surviving root unit
- if root unit is non-coherent, queue `RESOLVE_COHERENCY`

## UI Changes
UI must no longer infer top-level unit activation from the current phase.

Instead:

- UI looks for pending `SELECT_UNIT`
- clicking a unit resolves that pending request with `unit_id`
- engine then queues the next request
- UI renders the next request

For Movement phase:

- if pending `SELECT_UNIT` has `phase_step="MOVE_UNITS"`, clicking a battlefield unit resolves that request
- if pending `SELECT_UNIT` has `phase_step="REINFORCEMENTS"`, selecting a reserve unit resolves that request

UI remains responsible only for editing/submitting values for pending requests. It must not create those requests.

## Headless / Remote Implications
Headless controller must support `SELECT_UNIT` ranking by `phase_step`.

### Move Units ranking inputs
- objective pressure
- firing enablement
- charge enablement
- exposure / safety
- action economy

### Reinforcements ranking inputs
- reserve legality in current battle round
- placement safety
- objective pressure after arrival
- threat projection after arrival
- reserve-entry-specific heuristics

Remote/network behavior:

- `SELECT_UNIT` is just another authoritative request emitted to clients
- clients respond with `DecisionResult`
- engine validates and queues follow-up request deterministically

## Docs To Update
If/when implementation begins, update:

- `docs/DECISION_TYPES.md`
- `docs/NETWORK_SAVELOAD_DESIGN.md`
- `docs/DECISION_RECORD_TELEMETRY.md`

Recommended catalog changes:

- add `SELECT_UNIT`
- clarify `RESOLVE_COHERENCY` as post-casualty coherency remediation, not standard movement cleanup

Recommended UI mapping changes:

- movement unit activation list/click -> `SELECT_UNIT {unit_id}`
- reinforcements unit activation list/click -> `SELECT_UNIT {unit_id}`
- casualty coherency cleanup -> `RESOLVE_COHERENCY {model_id}`

## Testing Plan
### Unit tests
- `SELECT_UNIT` request generation for `MOVE_UNITS`
- `SELECT_UNIT` request generation for `REINFORCEMENTS`
- deterministic unit ordering and `pass` behavior
- invalid `unit_id` rejection for `SELECT_UNIT`
- invalid reinforcements selection rejection
- `MOVE_UNIT` resolution rejects invalid end states for:
  - out-of-bounds placement
  - terrain / wall collision
  - overlap with friendly or enemy models
  - non-coherent final unit layout
- movement validation rejects non-coherent end states
- reinforcements placement rejects non-coherent end states
- disembark validation rejects illegal setup after transport state restrictions
- embark follow-up only appears when every model ends within legal embark distance and embark restrictions are satisfied
- end-of-`MOVE_UNITS` bookkeeping marks untouched eligible units as `remained_stationary`
- legal pre-move disembark followed by no additional displacement counts as Normal move `0"` rather than `remained_stationary`
- legal post-transport-normal-move disembark counts the passenger unit as having made a Normal move
- casualty death queues `RESOLVE_COHERENCY` when unit becomes non-coherent
- repeated `RESOLVE_COHERENCY` loop ends when unit becomes coherent

### Integration tests
- headless Movement phase emits `SELECT_UNIT` in `MOVE_UNITS`
- headless Movement phase emits `SELECT_UNIT` in `REINFORCEMENTS`
- selecting an on-board unit in `MOVE_UNITS` queues `SELECT_MOVEMENT_ACTION`
- selecting an embarked passenger in `MOVE_UNITS` queues `DISEMBARK`
- selecting a reserve unit queues placement-style `MOVE_UNIT`
- legal post-move embark opportunities are represented without making `EMBARK` mutually exclusive with `MOVE_UNIT`
- ordinary movement never queues `RESOLVE_COHERENCY`
- casualty-driven coherency failure does queue `RESOLVE_COHERENCY`

### Regression tests
- self-play produces battle-phase activation records without UI dependency
- casualty resolution remains deterministic and replay-stable

## Recommended PR Breakdown
### PR 1 - Add `SELECT_UNIT` scaffolding
- add decision kind
- add handler
- add request builder helpers
- update docs

### PR 2 - Movement `MOVE_UNITS`
- queue `SELECT_UNIT` for `MOVE_UNITS`
- wire selection to `SELECT_MOVEMENT_ACTION`
- refactor local UI to resolve pending `SELECT_UNIT`
- update headless controller

### PR 3 - Movement `REINFORCEMENTS`
- queue `SELECT_UNIT` for `REINFORCEMENTS`
- wire selection to placement-style `MOVE_UNIT`
- enforce reserve-entry legality and battle-round restrictions
- update headless controller ranking

### PR 4 - Coherency remediation on casualties
- centralize post-death coherency checks
- queue `RESOLVE_COHERENCY` from authoritative engine
- remove any ordinary-movement use of `RESOLVE_COHERENCY`
- add casualty/removal tests

### PR 5 - Extend `SELECT_UNIT` to other phases
- Shooting
- Charge
- Fight
- replace or retire `SELECT_FIGHTER` as the main fight-phase activation decision

## Acceptance Criteria
- Engine, not UI, authors unit activation requests.
- Movement phase uses explicit `MOVE_UNITS` and `REINFORCEMENTS` step semantics.
- Headless play can resolve both Movement substeps with no UI dependency.
- Ordinary movement cannot end in non-coherent states.
- Casualty-driven coherency failures emit `RESOLVE_COHERENCY` until the unit becomes coherent or is destroyed.
- DecisionRecords remain deterministic and replay-safe across local, headless, and remote play.
