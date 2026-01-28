# Network + Save/Load Design (Battle Round 1+)

Status: Draft

## Goals

- Support deterministic network play (server authoritative, client UI) with replayable event logs.
- Support save/load at any point once battle round 1 has started.
- Ensure every UI dialog is a thin view over a decision/action API so headless play is possible.
- Keep engine state fully serializable, with stable references and predictable ordering.
- See `docs/NETWORK_GAMEPLAY.md` for lobby, role selection, and asyncio transport planning.

## Non-Goals

- Saving before battle round 1 begins (explicitly unsupported).
- Backwards compatibility for older save versions (versioned migrations only).
- Networking or persistence of UI-only state (dialogs, cursor positions, hovered items).

## Terminology

- Snapshot: Full serialized state of the game at a point in time.
- Command: A validated, deterministic input from a player/controller.
- Event: A deterministic state transition recorded in the log.
- DecisionRequest: A request emitted by the engine that must be answered before it can proceed.
- DecisionResult: The response that resolves a DecisionRequest.

## Determinism Rules

- All randomness flows through a single RandomSource; snapshot includes full RNG state.
- Dice rolls and rerolls are also recorded as deterministic events for replay and audit.
- All ordering over collections is deterministic (stable ID ordering).
- Coordinates are serialized in fixed-point units (1/1000 inch for positions/lengths; 1/10000 radians for facing).
- Derived/cached values are never serialized; they are recomputed on load.

## Entity Identity & Registries

Every entity that can be referenced across the network or in saved state gets a stable ID.

Entities requiring IDs:
- Player, Army
- Unit, Model
- Wargear instance (not just profile)
- Objective marker, Terrain piece, Token/Marker
- Ongoing Effect (aura, stratagem effect, once-per-phase flags)
- DecisionRequest, Command, Event

Registries:
- Each entity type has an ID->entity map.
- All references use IDs, not object pointers or names.
- If multiple datasheets share names, IDs disambiguate.

## Snapshot Schema (Versioned)

Top-level:
- schema_version
- fixed_point_scale
- angle_scale
- game: battle_round, phase, step, active_player_id
- players: CP, victory points, stratagem usage, once-per-battle flags
- map: terrain, objectives, boundaries, mission metadata
- units: state, positions, attachment relationships, embarked status
- units.round_state: includes declared charge targets (`charge_target_ids`) for multi-target charges
- units.models_cost: numeric bucket keys are normalized back to integers on load so point totals remain stable after snapshot/resync
- models: wounds, alive, position, base, wargear state
- effects: aura effects, temporary modifiers, timers
- decisions: pending DecisionRequests
- events: event log tail since last snapshot (currently full log)
- rng_state

Snapshot gating:
- Saving is allowed only when battle_round >= 1.
- If battle_round == 1 but pre-turn steps still running, saving is allowed.

## Event Log Schema

Events are serialized state transitions and random outcomes. Examples:
- command_applied, command_rejected
- decision_requested, decision_resolved
- dice_roll, roll_made, roll_rerolled
- unit_move_started, unit_move_ended
- model_destroyed, model_destroyed_before_removal, unit_destroyed
- phase_start, phase_end, battle_round_started
- objective_control_changed
- vp_awarded, vp_capped

Events include:
- event_id (monotonic int), type, actor_id
- deterministic payload (IDs + parameters)
- optional derived text for UI display (not used for state)

Note: The deterministic event log is separate from the UI EventSystem; UI-only signals
are not persisted or replayed.

## Command Schema

Commands are the only inputs accepted by the engine in headless mode.

Common command fields:
- command_id, request_id (if from DecisionRequest)
- actor_player_id
- target IDs (unit_id, model_id, target_unit_id)
- parameters (numbers, enum values, fixed-point coords)

Validation:
- Engine validates every command before applying.
- Invalid commands do not mutate state and produce error events.

DecisionResult command:
- `RESOLVE_DECISION` payload: `decision_id`, `option_id`, `result_payload` (optional dict)

DecisionRequest command:
- `REQUEST_DECISION` payload: `decision` (DecisionRequest dict with decision_id, decision_type, options, context)

Command execution:
- `Game.apply_command(...)` validates and dispatches commands through the engine dispatcher.
- `Game.process_command_queue(...)` drains queued commands in order for deterministic replay.
- Setup/phase progression and mission selection are now routed through command handlers.

## Decision/Action API (Core)

DecisionRequest:
- request_id
- actor_player_id
- decision_type (enum)
- context (phase, unit_id, target_id, weapon_id, etc)
- options (list of valid options with IDs and parameters)
- constraints (range, min/max, count limits)

DecisionResult:
- request_id
- chosen_option_id
- parameters (if option includes parameters)

## UI Dialog to Decision Mapping

Each dialog is a view over a DecisionRequest. The UI never mutates state directly.
Below is the mapping for all current dialogs. Each line is the decision type and
the required parameters (IDs and bounded values).

Setup / Mission:
- mission_selection_dialog: CHOOSE_MISSION {mission_id}
- mission_selection_modal: CHOOSE_MISSION {mission_id}
- side_by_side_modal: CONFIRM_MODAL {choice_id}

Deployment / Pre-battle:
- leader_attachment_dialog: ATTACH_LEADER {leader_unit_id, bodyguard_unit_id}
- reserves_allocation_dialog: DECLARE_RESERVES {unit_ids_by_bucket}
- transport_assignment_dialog: ASSIGN_TRANSPORT {unit_id, transport_id}
- hover_mode_prompt (yes_no_dialog): CONFIRM_YES_NO {unit_id, choice} (context `ability="hover_mode"`)
- nurgles_gift_plague_dialog: CHOOSE_PLAGUE {choice_id} (context `army_id`) (Declare Battle Formations)
- scout_choice_dialog: SCOUT_MOVE {unit_id, destination}
- floor_selection_dialog: SELECT_FLOOR {unit_id, floor_id}
- deployment_placement_dialog: MOVE_UNIT {unit_id, model_positions} (context `placement_kind="deployment"`, engine finalizes deployment + advances deployment turn)
- reserves_arrival_placement_dialog: MOVE_UNIT {unit_id, model_positions} (context `placement_kind="reserves_arrival"`, `allow_skip`, `battle_round`, `reserve_status`)

Command phase:
- shadow_in_the_warp_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="shadow_in_the_warp"`)
- waaagh_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="waaagh"`)

Movement:
- movement_choice_dialog: SELECT_MOVEMENT_ACTION {unit_id, action_type}
- individual_model_movement_dialog: MOVE_UNIT {unit_id, model_positions} (context may include `allowed_model_ids`, `placement_kind`, `allow_skip` for placement-only flows)
- coherency_violation_dialog: RESOLVE_COHERENCY {unit_id, fix_choice}
- transport_embark_dialog: EMBARK {unit_id, transport_id}
- transport_disembark_dialog: DISEMBARK {unit_id, transport_id, positions}
- transport_reactive_disembark_dialog: DISEMBARK {unit_id, transport_id, positions} (context `reactive_disembark_*`)
- battle_focus_opportunity_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (context `ability="battle_focus"`, `maneuver="opportunity"`)
- battle_focus_fade_back_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (context `ability="battle_focus"`, `maneuver="fade_back"`)
- setup_reactive_target_dialog: SELECT_SETUP_REACTIVE_TARGET {unit_id, target_unit_id | skip}
- setup_reactive_action_dialog: CHOOSE_SETUP_REACTIVE_ACTION {action}
- battlefield_point_pick_dialog: PICK_POINT {point}
- hazard_objective_select_dialog: PICK_OBJECTIVE {objective_id}
- move_over_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="move_over"`, `unit_id`, `model_id`, `ability_name`, `spec`)
Note: Reactive enemy-move abilities (e.g., Loping Speed / Scuttling Horrors) use `CONFIRM_YES_NO` with
`reactive_move_*` context, followed by `MOVE_UNIT` with `movement_type="loping_speed"` and `max_distance`
(rolled or fixed).
Blood Surge uses the same pattern with `reactive_move_kind="blood_surge"` and `movement_type="blood_surge"`.
Battle Focus reactive maneuvers first use `SELECT_OVERWATCH_SHOOTER` (context `ability="battle_focus"`),
then queue `MOVE_UNIT` with `movement_type="reactive"` and `max_distance`.
Fire and Fade and Reactive Reposition queue `MOVE_UNIT` with `movement_type="reactive"` and
`reactive_move_kind="fire_and_fade"` / `reactive_move_kind="reactive_reposition"`.
Setup reactive shoot/charge uses `DECLARE_SHOTS` with `out_of_phase=true` and `force_target_unit_id`.

Shooting:
- weapon_choice_dialog: SELECT_WEAPON {unit_id, weapon_id}
- shooting_declaration_dialog: DECLARE_SHOTS {unit_id, declarations[]}
- linked_fire_origin_dialog: DECLARE_SHOTS {unit_id, declarations[].linked_fire_origin_unit_id | None}
- deathstrike_action_dialog: DEATHSTRIKE_ACTION {unit_id, action, position?}
- firing_deck_dialog: DECLARE_FIRING_DECK {transport_id, declarations[]}
- overwatch_shooter_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (also used for stratagem unit selection; context may include enemy_unit_id)
- roll_reroll_dialog: REROLL_ROLL {roll_id, reroll_all_or_one, die_index}
Notes:
- DECLARE_SHOTS declarations include wargear_id, profile_name, model_ids, target_unit_id (optional for Plasma Warhead), linked_fire_origin_unit_id (optional for Linked Fire).

Charge:
- charge_declaration_dialog: DECLARE_CHARGE {unit_id, target_unit_ids[]}
- charge_end_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `mortal_wounds_kind="charge_end"`, `unit_id`, `ability_name`, `spec`)
- charge_phase_bodyguard_loss_dialog: ALLOCATE_DAMAGE {model_id} (context `selection_kind="bodyguard_loss"`, `leader_unit_id`, `bodyguard_unit_id`, `ability_name`)

Fight:
- fight_unit_selection_dialog: SELECT_FIGHTER {unit_id}
- fight_target_selection_dialog: SELECT_FIGHT_TARGETS {unit_id, target_unit_ids}
- fight_target_selection_dialog: SELECT_EXPLODING_HORRORS_TARGET {target_unit_id | skip} (context `unit_id`)
- fight_phase_end_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="fight_phase_end"`, `unit_id`, `model_id`, `ability_name`, `spec`)
- exploding_horrors_model_selection_dialog: SELECT_EXPLODING_HORRORS_MODELS {model_ids[]} (context `unit_id`, `target_unit_id`, `allowed_model_ids`)
- fight_within_3_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="fight_within_3"`, `unit_id`, `target_unit_id`)
- possessed_lord_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="possessed_lord"`, `unit_id`, `model_id`)
- melee_weapon_declaration_dialog: DECLARE_MELEE_WEAPONS {unit_id, weapon_bundles[]}
- melee_weapon_target_allocation_dialog: ALLOCATE_MELEE_TARGETS {bundle_id, target_unit_id}
- melee_target_allocation_dialog: ALLOCATE_TARGETS {unit_id, target_unit_ids}
- melee_attack_split_dialog: SPLIT_ATTACKS {bundle_id, split_plan[]}
- target_model_selection_dialog: SELECT_TARGET_MODEL {unit_id, target_model_id}
- precision_allocation_dialog: SELECT_PRECISION_TARGET {unit_id, target_model_id | bodyguard} (context `sequence_id`, `save_index`, `allowed_model_ids`)

Optional ability confirmations (yes/no):
- power_from_pain_command_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="power_from_pain_command"`)
- power_from_pain_empower_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="power_from_pain_empower"`, `unit_id`, `trigger`)
- enhancement_fight_first_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="enhancement_fight_first"`, `unit_id`)
- opponent_turn_strategic_reserves_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="opponent_turn_strategic_reserves"`, `unit_id`)
- seductive_gambit_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="seductive_gambit"`, `unit_id`)
- sensational_performance_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="sensational_performance"`, `unit_id`)
- cult_ambush_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="cult_ambush"`, `unit_id`)
- battle_focus_flitting_shadows_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_flitting_shadows"`, `unit_id`)
- battle_focus_sudden_strike_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_sudden_strike"`, `unit_id`)
- battle_focus_fade_back_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_fade_back"`, `unit_id`)
- cabal_channel_warp_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="cabal_channel_warp"`)
- stratagem_cp_discount_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="direct_the_slaughter"` or `ability="targeted_stratagem_discount"` or `ability="gift_of_foresight"` or `ability="master_of_the_pageant"`)
- power_from_pain_stratagem_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="power_from_pain_stratagem"`)

Dice Rolls:
- dice_roll_dialog: REQUEST_DICE_ROLL {roll_id, action_id="roll"}
- dice_roll_dialog (reroll): SELECT_DICE_REROLL {roll_id, action_id, selected_die_ids[]}
- damage_allocation_dialog: ALLOCATE_DAMAGE {unit_id, model_id} (context `selection_kind`, `allowed_model_ids`, `remaining_wounds`, `sequence_id`/`save_index` when tied to attack resolution)
  Selection kinds in use: `wound_allocation`, `hazardous`, `mortal_wound` (attack sequence), `unit_mortal_wound` (non-attack), `reverberating_summons_return`, `bodyguard_return`, `bodyguard_loss`.
- overwatch_shooter_dialog: SELECT_RISE_TO_CHALLENGE {unit_id | skip}

Faction / Detachment / Ability choices:
- blessings_of_khorne_dialog: CHOOSE_BLESSINGS {choices[]}
- blood_tithe_dialog: CHOOSE_BLOOD_TITHE {choice_id}
- cabal_of_sorcerers_dialog: CHOOSE_RITUALS {choices[]}
- code_chivalric_dialog: CHOOSE_CHIVALRIC_OATH {choice_id}
- daemonic_allegiance_dialog: CHOOSE_DAEMONIC_ALLEGIANCE {choice_id}
- dark_pacts_dialog: CHOOSE_DARK_PACT {choice_id}
- doctrina_imperatives_dialog: CHOOSE_DOCTRINA {choice_id}
- combat_doctrines_dialog: CHOOSE_COMBAT_DOCTRINE {choice_id | skip} (Combat Doctrines / Mastered Doctrines; availability validated by engine)
- grand_coven_dialog: CHOOSE_GRAND_COVEN {choice_id | skip}
- combat_drugs_dialog: CHOOSE_COMBAT_DRUGS {choice_id}
- hyper_adaptations_dialog: CHOOSE_HYPER_ADAPTATION {choice_id}
- frenzy_choice_dialog: CHOOSE_FRENZY_TARGET {target_unit_id}
- harbingers_of_dread_dialog: CHOOSE_HARBINGER {choice_id}
- martial_katah_dialog: CHOOSE_MARTIAL_KATAH {choice_id}
- gilded_champion_dialog: USE_GILDED_CHAMPION {action="use" | action="skip", model_id, ability_key}
- careen_choice_dialog: USE_CAREEN {choice="normal" | choice="fall_back" | action="skip", unit_id, model_id}
- miracle_dice_dialog: USE_MIRACLE_DIE {die_value | skip} (context `unit_id`, `roll_type`, `dice_count`, `die_faces`, `pool`, `needed`)
- nurgles_gift_plague_dialog: CHOOSE_PLAGUE {choice_id}
- pledge_selection_dialog: CHOOSE_PLEDGE {choice_id} (context `army_id`, `battle_round`, `max_value`, `ability_name="Pledges to the Dark Prince"`)
- quarry_selection_dialog: CHOOSE_QUARRY {target_unit_id} (context may include `ability`, `effect_key`, `source_unit_id`)
- modifier_ignore_dialog: CHOOSE_HIT_MODIFIER_IGNORES {choice} (context `attacker_model_id`, `target_unit_id`, `wargear_id`, `profile_name`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_SKILL_MODIFIER_IGNORES {choice} (context `attacker_model_id`, `target_unit_id`, `wargear_id`, `profile_name`, `ability_name`, `modifier_kind="weapon_skill"`)
- modifier_ignore_dialog: CHOOSE_MOVE_MODIFIER_IGNORES {choice} (context `unit_id`, `action_type`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_ADVANCE_MODIFIER_IGNORES {choice} (context `unit_id`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_CHARGE_MODIFIER_IGNORES {choice} (context `unit_id`, `target_unit_ids`, `ability_name`)
Note: modifier ignore dialogs are used by abilities like Driven by Ultimate Rage and Internal Rivalries. They are only requested when applicable modifiers exist, and their options are pruned to the relevant modifier signs.
- quarry_selection_dialog: CHOOSE_LIMB_FROM_LIMB {choice} (context `unit_id`)
- quarry_selection_dialog: CHOOSE_RED_WRATH {mode} (context `unit_id`)
- quarry_selection_dialog: PICK_OBJECTIVE {objective_id} (context `ability="a_grim_warning"`)
- secondary_discard_dialog: DISCARD_SECONDARY {card_id}
- shadow_form_dialog: CHOOSE_SHADOW_FORM {choice_id}
- templar_vows_dialog: CHOOSE_VOW {choice_id}
- voice_of_command_dialog: ISSUE_ORDER {unit_id, order_id}
- wrathful_presence_dialog: CHOOSE_WRATHFUL_PRESENCE {choice_id}
- yes_no_dialog: CONFIRM_YES_NO {choice}
- aspect_shrine_prompt_dialog: CHOOSE_ASPECT {choice_id}
- example_dialog: CONFIRM_EXAMPLE {choice_id}
- reverberating_summons_unit_dialog: SELECT_REVERBERATING_SUMMONS_UNIT {unit_id | skip}
- reverberating_summons_return_model_dialog: ALLOCATE_DAMAGE {unit_id, model_id | skip} (context `selection_kind="reverberating_summons_return"`)

Note: CAREEN! resolutions queue MOVE_UNIT with context `reactive_move_kind="careen"` and `movement_type="careen"`.

Note: All decision types must be validated in the engine and return errors if
the selected option is not currently legal.

## Headless Controller Contract

Headless play uses the same DecisionRequest and Command API:
- Engine emits DecisionRequest.
- Controller picks a DecisionResult and sends as a command.
- Engine validates, applies, and emits events.

This keeps AI and network clients identical to human UI behavior.

## Network Flow

- Server is authoritative.
- Client sends Command; server validates and emits Event(s).
- Server broadcasts Event(s) to all clients for visualization.
- Client UIs replay events to update local views.
- Server can push Snapshot + Event tail for resync.

## Network Message Schema (PR6)

Envelope:
- type
- protocol_version
- payload

Message payloads:
- Snapshot: { snapshot }
- Command: { command, client_last_event_id? }
- Event: { events[] }
- Error: { errors[], context? }
- Resync: { snapshot, events[], reason?, since_event_id? }

Round-trip validation (default):
- Server compares client_last_event_id to its current event_id.
- If mismatched or out of range, respond with Resync instead of applying the command.
- Otherwise apply the command and return Event(s); if rejected, also return Error.

Resync snapshots clear their embedded events list (events are sent separately in the Resync payload).

## Save/Load Flow

- Save is a Snapshot + (optional) Event tail.
- Load restores Snapshot, rehydrates registries, replays Event tail.
- On load, pending DecisionRequests are re-queued exactly once.
- Save/Load allowed only if battle_round >= 1.

## Session Storage (PR7)

Snapshots and event logs are stored under:
- `./games/data/<session_id>/`

Files:
- `manifest.json`: UX metadata (player stubs with id/control/agent_type, factions/detachments, battle round/phase, scores).
- `snapshot.json`: single snapshot per session (event log is embedded in the snapshot).

Cleanup:
- Manual only. No auto-pruning or expiry yet.
- Snapshot cadence: end of each phase (autosave).
- Event retention: keep only events since the most recent snapshot; flush on successful snapshot save.

## Snapshot Implementation Notes (PR2)

- Fixed-point scale is stored in the snapshot header for validation.
- Status effects serialization currently supports BattleShockEffect only.
- Objective conditions reload to a controlling-player check; custom condition logic is not persisted.
- Rule manager caches and UI hooks are excluded and rebuilt on load.

## Staged PR Plan

PR1: IDs and registries (Completed)
- Add stable IDs for all entities.
- Replace name-based references in engine state with IDs.
- Add deterministic ordering utilities.

PR2: Snapshot schema + serializer (Completed)
- Define schema_versioned snapshot.
- Implement serialization/deserialization with fixed-point coordinates.
- Exclude caches; rebuild on load.

PR3: Decision/Command API enforcement (Completed)
- Make engine accept only commands for state mutations.
- Convert existing direct UI mutations to commands.
- Emit DecisionRequests for every optional choice (dialog mapping in PR4).

PR4: Dialog integration (Completed)
- Map every dialog to a DecisionRequest type.
- Ensure UI uses the decision options payload.
- Add headless controller path for all dialogs.

PR5: Event log and replay (Completed)
- Emit deterministic events for commands, decisions, dice rolls/rerolls, movement, and destruction.
- Persist event log tail alongside snapshot and restore on load.
- Provide replay helper to run commands against a snapshot + event tail; add tests.

PR6: Network transport (Completed)
- Add server/client message types (Snapshot, Command, Event, Error, Resync).
- Implement round-trip validation and resync helpers.

PR7: Save/Load UX (Completed)
- Add save/load endpoints in engine API (no UI changes required here).
- Enforce battle_round >= 1 gating.
- API: Game.save_snapshot(), Game.load_snapshot(snapshot).

## Acceptance Criteria

- Any game state after battle round start can be snapshotted and reloaded with
  identical outcomes.
- Headless controller can complete a full game without UI.
- Two clients can remain in sync via server events and resync when needed.
- All dialogs are mirrored by DecisionRequests with explicit parameters.

## Open Questions

None.
