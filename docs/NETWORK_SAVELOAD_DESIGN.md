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
- Every game carries a single active rules bundle with atomic ids:
  `core_rules_id`, `rules_commentary_id`, `mission_pack_id`, `terrain_pack_id`,
  `dataslate_id`, `points_id`, `faction_pack_id`, `detachment_pack_id`, plus
  derived `rules_bundle_id`.

## Ruleset Bundle Versioning

Canonical ID source:
- Use the version string on page 1 of each official PDF.
- If the Core Rules PDF has no explicit version string, use the date token in the filename (e.g., `core_rules_24.09`).

Storage locations:
- Snapshot: `game.ruleset` includes all atomic rules ids plus `rules_bundle_id`.
- Event log: deterministic event payloads include the active bundle context.
- Decision context: every DecisionRequest context includes `rules_bundle` and `rules_bundle_id`.

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
- game.ruleset: core_rules_id, rules_commentary_id, mission_pack_id, terrain_pack_id, dataslate_id, points_id, faction_pack_id, detachment_pack_id, rules_bundle_id
- players: CP, victory points, stratagem usage, once-per-battle flags
- map: terrain, objectives, boundaries, mission metadata
- units: state, positions, attachment relationships, embarked status
- units.round_state: includes declared charge targets (`charge_target_ids`) for multi-target charges
- units.models_cost: numeric bucket keys are normalized back to integers on load so point totals remain stable after snapshot/resync
- models: wounds, alive, position, base, wargear state
- models.base: includes `model_height`, optional `z_offset`, and optional `compound_parts` for multi-part hull footprints (see `docs/MODEL_GEOMETRY_OVERRIDES.md`)
- effects: aura effects, temporary modifiers, timers
- decisions: pending DecisionRequests
- events: event log tail since last snapshot (in-memory log is bounded; default `10000` via `WH40K_EVENT_LOG_MAX`)
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
- `REQUEST_DECISION` payload: `decision` (DecisionRequest dict with decision_id, decision_type, options, candidates, mask, context)

Command execution:
- `Game.apply_command(...)` validates and dispatches commands through the engine dispatcher.
- `Game.process_command_queue(...)` drains queued commands in order for deterministic replay.
- Setup/phase progression and mission selection are now routed through command handlers.

## Decision/Action API (Core)

DecisionRequest:
- request_id
- actor_player_id
- decision_type (enum)
- context (phase, unit_id, target_id, weapon_id, rules_bundle, rules_bundle_id, descriptor_ids, etc)
- options (list of valid options with IDs and parameters)
- candidates (list of CandidateAction: action_id, params, metadata)
- mask (bool list aligned to candidates; false = illegal)
- mask_reasons (optional list aligned to candidates)
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
- settings_dialog: LOCAL_UI_SETTINGS {enable_developer_controls} (client-local UI state only; no engine command emitted)
- developer_menu_dialog: LOCAL_UI_TOOLING {profiling_enabled} (client-local debugging control; no engine command emitted)

Deployment / Pre-battle:
- player_color_picker_dialog: CHOOSE_PLAYER_COLOR {player_id, hue_degrees, rgb} (context `selection_kind="player_color"`, `hue_step_degrees=15`)
- leader_attachment_dialog: ATTACH_LEADER {leader_unit_id, bodyguard_unit_id}
- support_artillery_attachment_dialog: ATTACH_SUPPORT_ARTILLERY {support_unit_id, bodyguard_unit_id} (used for joined support/retinue attachments)
- reserves_allocation_dialog: DECLARE_RESERVES {unit_ids_by_bucket}
- transport_assignment_dialog: ASSIGN_TRANSPORT {unit_id, transport_id}
- shadow_assignment_dialog (quarry_selection_dialog): SHADOW_ASSIGNMENT {unit_id, replacement_datasheet_id | skip} (context `ability="shadow_assignment"`)
- hover_mode_prompt (yes_no_dialog): CONFIRM_YES_NO {unit_id, choice} (context `ability="hover_mode"`)
- nurgles_gift_plague_dialog: CHOOSE_PLAGUE {choice_id | skip} (context `army_id`; `ability="nurgles_gift_declare"` for Declare Battle Formations, or `ability="manifold_maladies"` with `battle_round` for start-of-battle-round detachment choice)
- daemonic_allegiance_dialog: CHOOSE_DAEMONIC_ALLEGIANCE {unit_id, keyword}
- start_of_battle_keyword_dialog: CHOOSE_START_OF_BATTLE_KEYWORD {keyword} (context `model_id`, `unit_id`, `ability_name`, `ability_key`)
- possessed_blade_weapon_dialog: CHOOSE_QUARRY {weapon_name} (context `ability="possessed_blade"`, `unit_id`, `model_id`, `ability_name`)
- scout_choice_dialog: SCOUT_MOVE {unit_id, destination}
- floor_selection_dialog: SELECT_FLOOR {unit_id, floor_id}
- deployment_placement_dialog: MOVE_UNIT {unit_id, model_positions} (context `placement_kind="deployment"`, engine finalizes deployment + advances deployment turn)
- reserves_arrival_placement_dialog: MOVE_UNIT {unit_id, model_positions} (context `placement_kind="reserves_arrival"`, `allow_skip`, `battle_round`, `reserve_status`)
- advance_redeploy_placement_dialog: MOVE_UNIT {unit_id, model_positions} (context `placement_kind="advance_redeploy_9h"`, `movement_type="advance"`, `allowed_model_ids[]`, `allow_skip=false`, `ability_name`)
- aeldari_guileful_strategist_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="aeldari_guileful_strategist"`, `redeploy_action`, `remaining`)
- auric_armour_walker_selection_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="solar_spearhead_walker_character_selection"`, `ability_name="Auric Armour"`, `phase="Muster Armies step"`, `army_id`, `allowed_unit_ids[]`, `max_units=2`)
- houndpack_lance_character_selection_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids} (context `ability="houndpack_lance_character_selection"`, `ability_name="Marked Prey"`, `phase="Muster Armies step"`, `army_id`, `allowed_unit_ids[]`, `max_units=3`, `required_units=3`)
- masters_of_misdirection_selection_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="deceptors_masters_of_misdirection_selection"`, `ability_name="Masters of Misdirection"`, `phase="Declare Battle Formations step"`, `army_id`, `allowed_unit_ids[]`, `max_units`, `max_units_per_type`)
- miasmic_bombardment_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="miasmic_bombardment"`, `ability_name="Miasmic Bombardment"`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`, `optional=true`)
- selected_leading_infiltrators_dialog: CHOOSE_QUARRY {selected_unit_id} (context `ability="army_selected_leading_infiltrators_declare"`, `ability_name`, `phase="Declare Battle Formations step"`, `army_id`, `candidate_unit_ids[]`, `optional=false`)

Command phase:
- shadow_in_the_warp_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="shadow_in_the_warp"`)
- waaagh_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="waaagh"`)
- combat_doctrines_dialog: CHOOSE_COMBAT_DOCTRINE {choice_key | skip} (context `army_id`, `battle_round`)
- mission_tactics_dialog: CHOOSE_MISSION_TACTIC {choice_key | skip} (context `army_id`, `battle_round`)
- angelic_legacy_dialog: CHOOSE_ANGELIC_LEGACY {choice_keys[2]} (context `army_id`, `battle_round`)
- grim_resolve_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="grim_resolve_target"`, `ability_name="Grim Resolve"`, `army_id`, `player_id`, `battle_round`, `phase="Command phase"`)
- huntress_eye_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="huntress_eye"`, `ability_name="Huntress' Eye"`, `army_id`, `command_phase_owner_id`, `source_unit_id`, `source_member_unit_id`, `source_model_id`, `range`)
- veteran_of_the_kataphraktoi_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="veteran_of_the_kataphraktoi"`, `ability_name="Veteran of the Kataphraktoi"`, `army_id`, `command_phase_owner_id`, `source_unit_id`, `source_member_unit_id`, `source_model_id`, `range`, `optional=true`)
- zealous_litanies_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="zealous_litanies"`, `ability_name="Zealous Litanies"`, `army_id`, `player_id`, `battle_round`, `allowed_choice_keys`, `optional=true`)
- grand_coven_dialog: CHOOSE_GRAND_COVEN {choice_key | skip} (context `army_id`, `battle_round`)
- combat_drugs_dialog: CHOOSE_COMBAT_DRUGS {choice_key} (context `army_id`, `battle_round`)
- labyrinthine_cunning_dialog: CHOOSE_QUARRY {action="spend_pain_token_gain_cp" | action="roll_d6_gain_cp" | skip} (context `ability="labyrinthine_cunning"`, `ability_name="Labyrinthine Cunning"`, `phase="Command phase"`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `pain_token_cost`, `cp_gain`, `success_on`, `optional=true`)
- conductor_of_torment_dialog: CHOOSE_QUARRY {action="gain_pain_token_and_switch_to_drukhari" | action="spend_pain_token_and_switch_to_harlequins" | skip} (context `ability="conductor_of_torment"`, `ability_name="Conductor of Torment"`, `phase="Command phase"`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `pain_tokens_gained`, `pain_token_cost`, `current_winning_side`, `optional=true`)
- experimental_augmentations_dialog: CHOOSE_QUARRY {mode="manual"+choice_key | mode="random"+choice_key="ROLL"} (context `ability="experimental_augmentations_choice"`, `ability_name="Experimental Augmentations"`, `army_id`, `battle_round`, `available_choice_keys[]`, `optional=false`)
- experimental_augmentations_reroll_dialog: CHOOSE_QUARRY {reroll_mode} (context `ability="experimental_augmentations_reroll"`, `ability_name="Experimental Augmentations"`, `army_id`, `battle_round`, `initial_rolls[]`, `available_reroll_modes[]`, `optional=false`)
- deceptors_falsehood_declare_dialog: CHOOSE_QUARRY {choice_key} (context `ability="deceptors_falsehood_declare_reserves"`, `ability_name="Falsehood"`, `phase="Declare Battle Formations step"`, `army_id`, `source_unit_id`, `source_model_id`, `allowed_choice_keys[]`, `optional=false`)
- deceptors_falsehood_reinforcements_dialog: CHOOSE_QUARRY {target_model_id | skip} (context `ability="deceptors_falsehood_reinforcements"`, `ability_name="Falsehood"`, `phase="Reinforcements step (Movement phase)"`, `army_id`, `source_unit_id`, `source_model_id`, `candidate_model_ids[]`, `optional=true`)
- deceptors_soul_link_dialog: CHOOSE_QUARRY {target_model_id | skip} (context `ability="deceptors_soul_link_target"`, `ability_name="Soul Link"`, `phase="Command phase"`, `army_id`, `source_unit_id`, `source_model_id`, `candidate_model_ids[]`, `optional=true`)
- forges_blessing_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="soulforged_warpack_forges_blessing_target"`, `ability_name="Forge's Blessing"`, `phase="Command phase"`, `army_id`, `source_unit_id`, `source_model_id`, `candidate_unit_ids[]`, `range`, `optional=false`)
- malevolent_heraldry_dialog: CHOOSE_QUARRY {reroll_mode} (context `ability="traitoris_malevolent_heraldry"`, `ability_name="Malevolent Heraldry"`, `army_id`, `battle_round`, `source_unit_id`, `initial_rolls[]`, `available_reroll_modes[]`, `optional=false`)
- tyrannical_motivation_dialog: CHOOSE_QUARRY {choice_key} (context `ability="tyrannical_motivation_choice"`, `ability_name="Tyrannical Motivation"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=false`)
- vendetta_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="renegade_warband_vendetta_target"`, `ability_name="Vendetta"`, `army_id`, `battle_round`, `candidate_unit_ids[]`, `optional=false`)
- focus_of_hatred_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="veterans_of_the_long_war_focus_of_hatred_target"`, `ability_name="Focus of Hatred"`, `army_id`, `battle_round`, `candidate_unit_ids[]`, `optional=false`)
- twisted_doctrine_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="renegade_warband_twisted_doctrine"`, `ability_name="Twisted Doctrine"`, `unit_id`, `trigger_action`, `set_up_as_reinforcements`, `turn`, `turn_owner_id`, `allowed_choice_keys[]`, `optional=true`)
- warmaster_dialog: CHOOSE_WARMASTER_ABILITY {choice_key} (context `unit_id`, `battle_round`, `player_id`, `expires_round`)
- voice_of_triarch_dialog: CHOOSE_QUARRY {choice_key} (context `ability="voice_of_triarch"`, `source_unit_id`, `battle_round`, `expires_round`, `player_id`, `allowed_choice_keys`)
- blood_tithe_dialog: CHOOSE_BLOOD_TITHE {ability_key | skip} (context `army_id`, `timing`)
- idols_of_khorne_dialog: CHOOSE_IDOL_OF_KHORNE {ability_key | skip} (context `army_id`, `timing`)
- here_be_loot_dialog: CHOOSE_QUARRY {objective_id} (context `ability="here_be_loot"`, `ability_name="Here Be Loot"`, `army_id`, `battle_round`, `candidate_objective_ids[]`, `optional=false`)
- integrated_tactics_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="integrated_tactics"`, `ability_name="Integrated Tactics"`, `phase="Shooting phase"`, `unit_id`, `source_unit_id`, `candidate_unit_ids[]`, `turn_owner`, `turn`, `optional=true`)
- final_day_psionic_parasitism_dialog: CHOOSE_QUARRY {gsc_unit_id+tyranids_unit_id | skip} (context `ability="final_day_psionic_parasitism"`, `ability_name="Psionic Parasitism"`, `phase="Movement phase"`, `unit_id`, `synapse_unit_id`, `candidate_pairs[]`, `turn_owner`, `turn`, `optional=true`)
- lissen_ere_dialog: CHOOSE_QUARRY {action="none" | target_unit_id+taktik} (context `ability="taktikal_brigade_lissen_ere"`, `ability_name="Lissen 'Ere"`, `army_id`, `issuer_model_id`, `issuer_model_name`, `issuer_unit_id`, `battle_round`, `trigger`, `candidate_unit_ids[]`, `candidate_taktiks[]`, `optional=true`)
- vessels_of_wrath_models_dialog: SELECT_VESSEL_OF_WRATH_MODELS {model_ids | skip} (context `army_id`, `battle_round`, `max_models`)
- wrath_of_khorne_blessing_dialog: CHOOSE_VESSEL_OF_WRATH_BLESSING {blessing_key} (context `army_id`, `battle_round`)
- realm_of_chaos_units_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `allowed_unit_ids`, `outside_shadow_unit_ids`, `max_units`) (used for The Realm of Chaos, Delirium Unmade, and Glimmershift Portal)
- informant_network_selection_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="informant_network_selection"`, `ability_name="Informant Network"`, `phase="Declare Battle Formations step"`, `army_id`, `allowed_unit_ids[]`, `max_units=3`, `optional=true`)
- oath_of_moment_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="oath_of_moment"`, `army_id`)
- bondsman_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="bondsman"`, `source_unit_id`)
- gate_warden_foundation_dialog: CHOOSE_QUARRY {objective_id} (context `ability="gate_warden_dauntless_defenders_foundation"`, `ability_name="Dauntless Defenders"`, `army_id`, `battle_round`, `slot_index`, `existing_foundation_ids[]`, `candidate_objective_ids[]`, `optional=false`)
- feed_the_swarm_dialog: CHOOSE_QUARRY {option_key | skip} (context `ability="feed_the_swarm"`, `ability_name="Feed the Swarm"`, `phase="Command phase"`, `army_id`, `source_unit_id`, `source_unit_name`, `option_keys[]`, `turn_owner_id`, `turn`)
- synaptic_imperatives_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="synaptic_imperatives"`, `ability_name="Synaptic Imperatives"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=true`)
- data_psalm_benediction_dialog: CHOOSE_QUARRY {choice_key} (context `ability="data_psalm_benediction"`, `ability_name="Benedictions Of The Omnissiah"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=false`)
- data_psalm_autosermon_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="data_psalm_autosermon"`, `ability_name="Data-blessed Autosermon"`, `ability_key`, `source_unit_id`, `source_member_unit_id`, `battle_round`, `allowed_choice_keys[]`, `optional=true`)
- battle_protocols_dialog: CHOOSE_QUARRY {battle_protocols_mode} (context `ability="battle_protocols"`, `ability_name="Battle Protocols"`, `source_unit_id`, `allowed_modes[]`, `current_mode`, `phase="Command phase"`, `optional=true`)
- canticles_of_the_omnissiah_dialog: CHOOSE_QUARRY {canticles_mode, canticles_mode_key} (context `ability="canticles_of_the_omnissiah"`, `ability_name="Canticles of the Omnissiah"`, `source_unit_id`, `phase="Command phase"`, `optional=false`)
- invocation_of_machine_vengeance_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="canticles_machine_vengeance_target"`, `ability_name="Invocation of Machine Vengeance"`, `source_unit_id`, `candidate_unit_ids[]`, `phase="Command phase"`, `optional=false`)
- acquisition_at_any_cost_dialog: CHOOSE_QUARRY {objective_id} (context `ability="acquisition_at_any_cost"`, `ability_name="Acquisition At Any Cost"`, `army_id`, `battle_round`, `candidate_objective_ids[]`, `optional=false`)
- noospheric_transference_units_dialog: CHOOSE_QUARRY {selected_unit_ids[]} (context `ability="noospheric_transference_units"`, `ability_name="Noospheric Transference"`, `army_id`, `battle_round`, `candidate_unit_ids[]`, `max_selections`, `optional=false`)
- noospheric_transference_override_dialog: CHOOSE_QUARRY {choice_key} (context `ability="noospheric_transference_override"`, `ability_name="Noospheric Transference"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=false`)
- necrons_command_phase_dialog: CHOOSE_QUARRY {target_unit_id} (context `necrons_command_phase_enhancement=true`, `source_unit_id`, `ability`, `effect_key`, `effect_value`)
- worthy_foes_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="worthy_foes"`, `ability_name="Worthy Foes"`, `army_id`)
- cosmic_distortion_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="cosmic_distortion_phase_surge"`, `ability_name="Cosmic Distortion"`, `army_id`, `phase_key`, `phase_name`, `allowed_unit_ids[]`, `max_units`)
- artillery_support_mode_dialog: CHOOSE_QUARRY {artillery_support_mode} (context `ability="siege_regiment_artillery_support_mode"`, `ability_name="Artillery Support"`, `army_id`, `battle_round`, `allowed_modes[]`, `max_units`, `optional=false`)
- artillery_support_incendiary_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="siege_regiment_incendiary_bombardment"`, `ability_name="Incendiary Bombardment"`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`, `optional=true`)
- artillery_support_smoke_shells_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="siege_regiment_smoke_shells"`, `ability_name="Smoke Shells"`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`, `optional=true`)
- artillery_support_creeping_selection_dialog: SELECT_REALM_OF_CHAOS_UNITS {unit_ids} (context `ability="siege_regiment_creeping_barrage_selection"`, `ability_name="Creeping Barrage"`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`, `required_units`, `optional=false`)
- resurrection_orb_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="resurrection_orb"`, `source_unit_id`, `bearer_model_id`, `resurrection_orb_variant`, `allowed_target_unit_ids`, `optional=true`)
- aeldari_lucid_eye_dialog: CHOOSE_QUARRY {die_index + delta | skip} (context `ability="aeldari_lucid_eye_fate_die"`, `source_unit_id`, `model_id`, `optional=true`)
- aeldari_spirit_stone_heal_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="aeldari_spirit_stone_heal"`, `source_unit_id`, `model_id`, `range`)
- aeldari_light_of_clarity_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="aeldari_light_of_clarity_target"`, `source_unit_id`, `model_id`, `range`, `infantry_bonus`, `monster_bonus`)
- aeldari_stave_of_kurnous_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="aeldari_stave_of_kurnous_target"`, `source_unit_id`, `model_id`, `range`, `exclude_titanic`)
- aeldari_rune_of_mists_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="aeldari_rune_of_mists_target"`, `source_unit_id`, `model_id`, `range`, `min_attacker_distance_for_cover`)
- space_marines_wolf_master_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="space_marines_wolf_master_target"`, `ability_name="Wolf Master"`, `source_unit_id`, `model_id`, `range=9`, `weapon_names[]`)
- tears_of_isha_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="tears_of_isha_target"`, `source_unit_id`, `model_id`, `range`, `keyword`)
- master_of_mechanisms_dialog: CHOOSE_QUARRY {target_unit_id | target_model_id | skip} (context `ability="master_of_mechanisms"`, `source_unit_id`, `model_id`, `range`, `hit_bonus`, `fnp_value`, `fnp_requires_vehicle`, `target_requires_vehicle`, optional `target_keyword`, optional `selection_kind`, optional `limit_once_per_turn`, optional `limit_scope`, `turn_owner`, `turn`, `optional=true`)
- surrogate_hosts_dialog: CHOOSE_QUARRY {target_model_id | skip} (context `ability="surrogate_hosts"`, `ability_name="Surrogate Hosts"`, `source_unit_id`, `source_model_id`, `candidate_model_ids[]`, `required_keywords_all[]`, `excluded_unit_names[]`, `exclude_epic_hero`, `attach_if_target_was_leading`, `turn_owner`, `turn`, `optional=true`)
- paragon_of_sanctity_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="paragon_of_sanctity"`, `source_unit_id`, `model_id`, `ability_key`, `range=18`, `optional=true`)
- righteous_purpose_dialog: CHOOSE_QUARRY {selected_unit_ids[0..3] | skip} (context `ability="righteous_purpose"`, `ability_name="Righteous Purpose"`, `army_id`, `candidate_unit_ids[]`, `max_selections=3`, `optional=true`)
- desperate_for_redemption_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="desperate_for_redemption"`, `ability_name="Desperate for Redemption"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=true`)
- divine_aspect_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="divine_aspect_target"`, `ability_name="Divine Aspect"`, `army_id`, `source_unit_id`, `source_model_id`, `range_inches=12`, `candidate_unit_ids[]`, `phase="Movement phase"`, `optional=true`)
- code_chivalric_dialog: CHOOSE_CHIVALRIC_OATH {choice_key} (context `oath_kind`, `army_id`)
- code_chivalric_target_dialog: SELECT_TARGET_MODEL {model_id} (context `selection_kind="code_chivalric_target"`)
- malefic_surge_unit_dialog: CHOOSE_MALEFIC_SURGE_UNIT {unit_id | skip} (context `ability="malefic_surge"`, `battle_round`)
- soulless_horror_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="soulless_horror"`, `unit_id`, `model_id`, `ability_key`, `range`, `test_penalty`, `psyker_test_penalty`)
- harbinger_of_despair_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="harbinger_of_despair_battleshock"`, `ability_name`, `ability_key`, `phase_name`, `unit_id`, `model_id`, `range`, `test_penalty`, `candidate_unit_ids[]`, `optional=true`, `once_per_turn=true`, `turn`)
- fight_phase_engagement_battleshock_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="fight_phase_select_engagement_battleshock"`, `ability_name`, `ability_key`, `phase_name="FIGHT_PHASE"`, `unit_id`, `model_id`, `engagement_only=true`, optional `test_penalty`, `candidate_unit_ids[]`, `optional`, `once_per_turn`, `turn`)
- fight_phase_enemy_melee_hit_penalty_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="fight_phase_select_enemy_melee_hit_penalty"`, `ability_name`, `ability_key`, `phase_name="FIGHT_PHASE"`, `unit_id`, `source_unit_id`, `model_id`, `engagement_only=true`, `hit_penalty`, `candidate_unit_ids[]`, `optional`, `once_per_turn`, `turn`)
- glovodan_psyber_eagle_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="post_shoot_no_cover"`, `ability_name="Glovodan Psyber-eagle"`, `ability_key="command_phase_no_cover:glovodan_psyber_eagle"`, `phase="Command phase"`, `unit_id`, `source_unit_id`, `attacker_unit_id`, `model_id`, `range=18`, `candidate_unit_ids[]`, `expires_timing="OWNER_NEXT_COMMAND_START"`, `optional=true`, `turn`)
- psychic_veil_dialog: CHOOSE_QUARRY {action="use" | skip} (context `ability="imperial_agents_psychic_veil"`, `ability_name="Psychic Veil (Psychic)"`, `ability_key`, `phase="Command phase"`, `unit_id`, `source_unit_id`, `model_id`, `targeting_range=18`, `optional=true`, `turn`)

Movement:
- movement_choice_dialog: SELECT_MOVEMENT_ACTION {unit_id, action_type}
- pre_normal_move_bonus_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="movement_phase_move_weapon_bonus"`, `unit_id`, `model_id`, `move_bonus_dice`, `move_bonus_flat`, `attacks_bonus`, `weapon_name`, `buff_key`)
- pre_normal_move_flickerjump_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="flickerjump"`, `unit_id`, `move_value`)
- cloudstrider_deep_strike_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="cloudstrider"`, `unit_id`, `ability_name`)
- malefic_surge_movement_dialog: CHOOSE_MALEFIC_SURGE_ABILITY {choice | skip} (context `ability="malefic_surge"`, `unit_id`, `trigger="movement"`)
- decoy_targets_dialog: CHOOSE_QUARRY {target_model_id | skip} (context `ability="decoy_targets"`, `ability_name`, `phase="Movement phase"`, `source_unit_id`, `source_model_id`, `max_uses`, `per_battle_round_limit`, `optional=true`)
- a_foot_in_the_future_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="a_foot_in_the_future"`, `ability_name="A Foot in the Future"`, `phase="Movement phase"`, `source_unit_id`, `target_unit_id`, `candidate_unit_ids[]`, `move_roll`, `no_charge_this_turn`, `turn_owner_id`, `turn`, `optional=true`)
- vowed_target_dialog: CHOOSE_QUARRY {mode, objective_ids[1+], signature} (context `ability="vowed_target_selection"`, `ability_name="Vowed Target"`, `phase="Movement phase"`, `army_id`, `player_id`, `battle_round`, `candidate_signatures`)
- movement_phase_wound_bonus_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="movement_phase_visible_wound_bonus"`, `unit_id`, `model_id`, `range`, `keyword`, `bonus`)
- movement_phase_hit_bonus_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="movement_phase_visible_hit_bonus"`, `unit_id`, `model_id`, `range`, `keyword`, `bonus`)
- prescient_redeployment_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="prescient_redeployment"`, `ability_name="Prescient Redeployment"`, `phase="Movement phase"`, `optional=true`, `max_units`, `selected_last_gate`, `remaining_capacity`)
- misfortune_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="misfortune"`, `source_unit_id`, `model_id`, `range`, `penalty`)
- nurgles_rot_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="nurgles_rot"`, `source_unit_id`, `model_id`, `range`, `penalty`)
- diseased_influence_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="diseased_influence"`, `ability_name`, `source_unit_id`, `moving_unit_id`, `turn`, `optional=true`)
- symphony_of_pain_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="symphony_of_pain"`, `source_unit_id`, `model_id`, `range`, `keywords`)
- grenade_pack_flyover_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="grenade_pack_flyover"`, `unit_id`, `range`, `threshold`, `mortal_per_success`, `max_mortal`)
- sublime_prescience_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="sublime_prescience"`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `optional=true`)
- spirit_mark_friendly_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="spirit_mark_friendly"`, `source_unit_id`, `model_id`, `range`, `keyword`, `sustained_hits_value`)
- spirit_mark_enemy_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="spirit_mark_enemy"`, `source_unit_id`, `model_id`, `friendly_unit_id`, `sustained_hits_value`, `keyword`)
- individual_model_movement_dialog: MOVE_UNIT {unit_id, model_positions} (context may include `allowed_model_ids`, `placement_kind`, `allow_skip` for placement-only flows)
- coherency_violation_dialog: RESOLVE_COHERENCY {unit_id, fix_choice}
- transport_embark_dialog: EMBARK {unit_id, transport_id}
- transport_disembark_dialog: DISEMBARK {unit_id, transport_id, positions}
- transport_reactive_disembark_dialog: DISEMBARK {unit_id, transport_id, positions} (context `reactive_disembark_*`)
- battle_focus_opportunity_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (context `ability="battle_focus"`, `maneuver="opportunity"`)
- battle_focus_fade_back_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (context `ability="battle_focus"`, `maneuver="fade_back"`)
- battle_focus_lethal_surge_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="aeldari_strength_from_death_lethal_surge"`, `unit_id`, `attacker_unit_id`, `turn`, `turn_owner_id`)
- battle_focus_maneuver_dialog: CHOOSE_BATTLE_FOCUS_MANEUVER {choice_key | skip} (context `unit_id`, `trigger="move"`, `action`)
- setup_reactive_target_dialog: SELECT_SETUP_REACTIVE_TARGET {unit_id, target_unit_id | skip}
- setup_reactive_action_dialog: CHOOSE_SETUP_REACTIVE_ACTION {action}
- battlefield_point_pick_dialog: PICK_POINT {point}
- fleet_commander_first_marker_dialog: PICK_POINT {point | skip} (context `ability="fleet_commander_marker_1"`, `ability_name="Fleet Commander"`, `unit_id`, `source_member_unit_id`, `ability_key`, `marker_range`, `roll_min`, `mortal_wounds_roll`, `optional=true`)
- fleet_commander_second_marker_dialog: PICK_POINT {point} (context `ability="fleet_commander_marker_2"`, `ability_name="Fleet Commander"`, `unit_id`, `source_member_unit_id`, `first_marker_point`, `marker_range`, `roll_min`, `mortal_wounds_roll`, `optional=false`)
- parasitic_infection_spawn_dialog: PICK_POINT {point | skip} (context `ability="parasitic_infection_spawn"`, `ability_name="Parasitic Infection"`, `source_unit_id`, `source_model_id`, `target_unit_id`, `spawn_unit_name="Ripper Swarms"`, `spawn_model_count_roll`, `spawn_model_count`, `setup_range`, `trigger_id`, `optional=true`)
- hazard_objective_select_dialog: PICK_OBJECTIVE {objective_id}
- move_over_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="move_over"`, `unit_id`, `model_id` optional, `ability_name`, `spec`)
- stasis_bomb_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="stasis_bomb"`, `unit_id`, `ability_name`, `spec.source_model_ids_by_target`, `spec.once_per_turn_army`, `spec.once_per_battle_per_model`)
- bomb_squigs_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="bomb_squigs"`, `unit_id`, `ability_name`, `spec.max_uses`, `spec.remaining_uses`)
- plunder_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="plunder"`, `unit_id`, `ability_name`, `spec`)
- cult_ambush_reinforcements_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="cult_ambush_reinforcements"`, `marker_id`, `remaining_marker_ids`, `available_unit_ids`)
Battle-shock:
- cankerblight_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="cankerblight"`, `target_unit_id`, `source_unit_id`, `source_model_id`)
- cankerblight_model_dialog: SELECT_TARGET_MODEL {model_id} (context `selection_kind="cankerblight_destroy"`, `target_unit_id`, `source_unit_id`, `ability_name`)
- fear_made_manifest_dialog: CHOOSE_QUARRY {destroy_count | destroy_count_roll} (context `ability="fear_made_manifest"`, `target_unit_id`, `source_unit_id`, `source_model_id`, optional `once_key`, optional `once_roll`, optional `can_use_once`)
- fear_made_manifest_model_dialog: SELECT_TARGET_MODEL {model_id} (context `selection_kind="fear_made_manifest_destroy"`, `target_unit_id`, `source_unit_id`, `ability_name`, `destroy_remaining`)
Note: Reactive enemy-move abilities (e.g., Loping Speed / Scuttling Horrors) use `CONFIRM_YES_NO` with
`reactive_move_*` context, followed by `MOVE_UNIT` with `movement_type="loping_speed"` and `max_distance`
(rolled or fixed).
Blood Surge uses the same pattern with `reactive_move_kind="blood_surge"` and `movement_type="blood_surge"`.
Brazen Fury uses the same pattern with `reactive_move_kind="brazen_fury"` and `movement_type="brazen_fury"`.
Horde Move uses the same pattern with `reactive_move_kind="horde_move"` and `movement_type="horde_move"`.
Blistering Assault uses the same pattern with `reactive_move_kind="blistering_assault"` and `movement_type="blistering_assault"` (with `reactive_move_allow_engagement_range=true`).
Battle Focus reactive maneuvers first use `SELECT_OVERWATCH_SHOOTER` (context `ability="battle_focus"`),
then queue `MOVE_UNIT` with `movement_type="reactive"` and `max_distance`. Devoted of Ynnead
Lethal Surge uses a `CONFIRM_YES_NO` step and queues `MOVE_UNIT` with
`reactive_move_kind="aeldari_strength_from_death_lethal_surge"` and
`reactive_move_allow_engagement_range=true`.
Fire and Fade and Reactive Reposition queue `MOVE_UNIT` with `movement_type="reactive"` and
`reactive_move_kind="fire_and_fade"` / `reactive_move_kind="reactive_reposition"`.
Tactical Acumen queues `MOVE_UNIT` with `movement_type="reactive"` and `reactive_move_kind="tactical_acumen"`.
A Foot in the Future queues `MOVE_UNIT` with `movement_type="reactive"` and `reactive_move_kind="a_foot_in_the_future"` (max distance from the recorded D6 roll).
Gleaming Pinions uses `CONFIRM_YES_NO` then queues `MOVE_UNIT` with `movement_type="gleaming_pinions"` and `reactive_move_kind="gleaming_pinions"`.
Martial Philosopher uses `CONFIRM_YES_NO` then queues `MOVE_UNIT` with `movement_type="martial_philosopher"` and `reactive_move_kind="martial_philosopher"`.
Setup reactive shoot/charge uses `DECLARE_SHOTS` with `out_of_phase=true` and `force_target_unit_id`.

Shooting:
- weapon_choice_dialog: SELECT_WEAPON {unit_id, weapon_id}
- shooting_declaration_dialog: DECLARE_SHOTS {unit_id, declarations[]}
- linked_fire_origin_dialog: DECLARE_SHOTS {unit_id, declarations[].linked_fire_origin_unit_id | None, declarations[].linked_fire_mode}
- deathstrike_action_dialog: DEATHSTRIKE_ACTION {unit_id, action, position?}
- repair_barge_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="repair_barge"`, `source_unit_id`, `model_id`, `range=3`, `allowed_target_unit_ids`, `turn_owner`, `turn`, `optional=true`)
- post_shoot_crit_hit_threshold_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_crit_hit_threshold"`, `attacker_unit_id`, `model_id`, `keyword`, `threshold`)
- firing_deck_dialog: DECLARE_FIRING_DECK {transport_id, declarations[]}
- overwatch_shooter_dialog: SELECT_OVERWATCH_SHOOTER {unit_id} (also used for stratagem unit selection; context may include enemy_unit_id)
- roll_reroll_dialog: REROLL_ROLL {roll_id, reroll_all_or_one, die_index}
- dark_pacts_dialog: CHOOSE_DARK_PACT {choice, optional `empyric_wellspring_choice`, optional `invoke_contract` | skip} (context `unit_id`, `phase_name`, `trigger`; Cabal of Chaos requires `empyric_wellspring_choice`; Soulforged Warpack eligible DAEMON VEHICLE units may set `invoke_contract=true`)
- dread_mob_try_dat_button_shooting_dialog: CHOOSE_QUARRY {button_mode, button_effect?} (context `ability="dread_mob_try_dat_button"`, `ability_name="Try Dat Button!"`, `army_id`, `unit_id`, `phase_name`, `trigger="shooting"`, `candidate_button_modes[]`, `candidate_button_effects[]`, `optional=false`)
- path_of_warrior_dialog: CHOOSE_PATH_OF_WARRIOR {choice_key} (context `unit_id`, `phase_name`, `trigger`)
- cruel_amusement_dialog: CHOOSE_CRUEL_AMUSEMENT {choice} (context `unit_id`, `model_id`, `weapon_name`, `ability_name`)
- master_of_magicks_dialog: CHOOSE_MASTER_OF_MAGICKS {choice} (context `unit_id`, `model_id`, `weapon_name`, `ability_name`)
- technosorcerous_augmentations_dialog: CHOOSE_TECHNOSORCEROUS_AUGMENTATION {choice} (context `unit_id`, `ability_name`, `phase_name`)
- hand_of_asuryan_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="hand_of_asuryan"`, `unit_id`, `model_id`, `weapon_name`, `ability_name`)
- shieldbreaker_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="shieldbreaker"`, `unit_id`, `model_id`, `ability_key`, `weapon_name`, `wound_bonus`)
- dark_blessings_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="start_any_phase_invulnerable_save"`, `unit_id`, `model_id`, `buff_key`, `invuln`; triggered after enemy target selection in Shooting/Fight)
- iron_resolve_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="start_any_phase_fnp"`, `unit_id`, `ability_key`, `fnp_value`, `trigger_action`; triggered after bearer unit is selected as a target in Shooting/Fight)
- troubling_visions_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="troubling_visions"`, `unit_id`, `source_member_unit_id`, `ability_key`, `expires_round`; triggered in the owner's Command phase)
- student_of_the_codex_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="student_of_the_codex"`, `unit_id`, `source_member_unit_id`, `model_id`, `doctrine`, `expires_round`; triggered in the owner's Command phase)
- malefic_surge_diabolic_power_dialog: CHOOSE_MALEFIC_SURGE_ABILITY {choice | skip} (context `ability="malefic_surge"`, `unit_id`, `trigger="shooting"`)
- malefic_surge_unnatural_fortitude_dialog: CHOOSE_MALEFIC_SURGE_ABILITY {choice | skip} (context `ability="malefic_surge"`, `unit_id`, `trigger="targeted_shooting"`)
- warpmeld_sacrifice_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="warpmeld_sacrifice"`, `unit_id`, `ability_mode`, `trigger_action`, `source_unit_id`, `turn`, `turn_owner_id`)
- maggot_maws_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="maggot_maws"`, `source_unit_id`, `model_id`, `range`)
- crucible_of_malediction_dialog: CHOOSE_QUARRY {action="use" | action="use_and_spend_pain_token" | skip} (context `ability="crucible_of_malediction"`, `ability_name="Crucible of Malediction"`, `phase="Shooting phase"`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `range`, `candidate_unit_ids[]`, `pain_token_cost`, `battle_shock_test_modifier_if_spent`, `psyker_fail_mortal_wounds`, `once_key`, `optional=true`)
- aeldari_guiding_presence_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="aeldari_guiding_presence"`, `source_unit_id`, `model_id`, `range`, `bonus`)
- unleash_hell_vehicle_dialog: SELECT_UNLEASH_HELL_VEHICLE {unit_id | skip} (context `ability="unleash_hell"`, `source_unit_id`, `bearer_model_id`, `range`, `allowed_unit_ids`, `exclude_monster_vehicle`)
- iron_ambassador_dialog: CHOOSE_QUARRY {spend_yp | skip} (context `ability="iron_ambassador"`, `unit_id`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `optional=true`)
- bastion_shield_dialog: CHOOSE_QUARRY {spend_yp | skip} (context `ability="bastion_shield"`, `unit_id`, `source_unit_id`, `source_member_unit_id`, `attacker_unit_id`, `turn_owner`, `turn`, `optional=true`)
- accomplished_tactician_dialog: CHOOSE_QUARRY {target_unit_id + transport_unit_id | skip} (context `ability="accomplished_tactician"`, `source_unit_id`, `model_id`, `range`, `embark_range`, `turn_owner`, `turn`, `optional=true`)
- post_shoot_battleshock_target_dialog: CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`)
- start_shooting_battleshock_target_dialog: CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET {target_unit_id} (context `source_unit_id`, `model_id`, `ability_name`, `range`, optional `use_leadership_test`, `leadership_test_modifier_if_battle_shocked`, `fail_mortal_wounds`; used by abilities including `Pledge of Mortal Pain`)
- battleshock_clear_target_dialog: CHOOSE_BATTLESHOCK_CLEAR_TARGET {unit_id | skip} (context `source_unit_id`, `model_id`, `ability_name`, `ability_key`, `range`, `phase`)
- post_shoot_mortal_wounds_target_dialog: CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`, `dice`, `threshold`, `mortal_per_success`)
- post_shoot_wracked_agonies_target_dialog: CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`, `move_penalty`, `charge_penalty`)
- post_shoot_aflame_target_dialog: CHOOSE_POST_SHOOT_AFLAME_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`, `move_penalty`, `advance_penalty`, `charge_penalty`, `roll_threshold`)
- post_shoot_suppression_target_dialog: CHOOSE_POST_SHOOT_SUPPRESSION_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`)
- quake_multigenerator_target_dialog: CHOOSE_POST_SHOOT_SUPPRESSION_TARGET {target_unit_id} (context `ability="quake_multigenerator"`, `attacker_unit_id`, `model_id`, `ability_name`)
- post_shoot_no_cover_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_no_cover"`, `attacker_unit_id`, `ability_name`, `weapon_key`, optional `source_model_id` for bearer-scoped effects)
- first_failed_save_damage_zero_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="first_failed_save_damage_zero"`, `ability_name`, `usage_key`; used by optional once-per-scope failed-save damage-to-zero effects such as Bastion Plate)
- post_shoot_ap_bonus_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_ap_bonus"`, `attacker_unit_id`, `ability_name`, `keyword`, `attack_type`, `ap_bonus`, `limit_scope`)
- post_shoot_snare_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_snare"`, `attacker_unit_id`, `model_id`, `ability_name`, `weapon_key`)
- post_shoot_shocked_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_shocked"`, `attacker_unit_id`, `ability_name`, `move_penalty`, `advance_penalty`, `charge_penalty`)
- post_shoot_disembark_wound_reroll_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="post_shoot_disembark_wound_reroll"`, `attacker_unit_id`, `model_id`, `ability_name`)
- inflamed_reprisal_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="inflamed_reprisal"`, `ability_name`, `source_unit_id`, `attacker_unit_id`, `turn`, `optional=true`)
- post_shoot_leadership_debuff_target_dialog: CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET {target_unit_id} (context `attacker_unit_id`, `ability_name`)
- daemonic_poisons_target_dialog: CHOOSE_DAEMONIC_POISONS_TARGET {target_unit_id} (context `attacker_unit_id`, `model_id`, `ability_name`, `phase`)
- gift_of_chaos_target_dialog: CHOOSE_GIFT_OF_CHAOS_TARGET {target_unit_id} (context `ability="gift_of_chaos"`, `attacker_unit_id`, `model_id`, `ability_name`, `phase`)
- spirit_thief_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="spirit_thief"`, `source_unit_id`, `model_id`, `ability_name`, `keyword`, `range`)
- corrupt_machine_spirits_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="corrupt_machine_spirits"`, `source_unit_id`, `model_id`, `ability_name`, `range`)
Other (any phase):
- power_from_pain_option_dialog: CHOOSE_POWER_FROM_PAIN_OPTION {choice_key} (context `unit_id`, `choice_kind`, `pending_key`; choice kinds include `archon_poisoned_tongue`, `experimental_enhancements`, `master_regenesist`, `sadistic_fulcrum_transport` where `choice_key` is selected `transport_unit_id` or `NONE`)
- piratical_raiders_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="piratical_raiders"`, `source_unit_id`, `ability_name`)
Notes:
- DECLARE_SHOTS declarations include wargear_id, profile_name, model_ids, target_unit_id (optional for Plasma Warhead), linked_fire_origin_unit_id (optional for Linked Fire / Infernal Puppeteer), linked_fire_mode ("linked_fire" | "infernal_puppeteer" when origin is provided).

Charge:
- charge_declaration_dialog: DECLARE_CHARGE {unit_id, target_unit_ids[]}
- charge_end_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `mortal_wounds_kind="charge_end"`, `unit_id`, `ability_name`, `spec`)
- charge_phase_bodyguard_loss_dialog: ALLOCATE_DAMAGE {model_id} (context `selection_kind="bodyguard_loss"`, `leader_unit_id`, `bodyguard_unit_id`, `ability_name`)

Fight:
- fight_unit_selection_dialog: SELECT_FIGHTER {unit_id}
- fight_target_selection_dialog: SELECT_FIGHT_TARGETS {unit_id, target_unit_ids}
- fight_target_selection_dialog: SELECT_EXPLODING_HORRORS_TARGET {target_unit_id | skip} (context `unit_id`)
- eye_of_spite_dialog: CHOOSE_QUARRY {action="spend_pain_token" | skip} (context `ability="eye_of_spite"`, `ability_name="Eye of Spite"`, `phase="Fight phase"`, `source_unit_id`, `model_id`, `turn_owner`, `turn`, `pain_token_cost`, `optional=true`)
- fight_phase_end_mortal_wounds_target_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `mortal_wounds_kind="fight_phase_end"`, `unit_id`, `model_id`, `ability_name`, `spec`)
- curse_of_walking_pox_dialog: CHOOSE_QUARRY {returns | skip} (context `ability="curse_of_walking_pox"`, `ability_name`, `source_unit_id`, `unit_id`, `max_returns`, `turn_owner`, `turn`, `phase`, `optional=true`)
- end_of_fight_embark_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="end_of_fight_embark"`, `transport_id`, `range`, `max_models`, `keyword`)
- exploding_horrors_model_selection_dialog: SELECT_EXPLODING_HORRORS_MODELS {model_ids[]} (context `unit_id`, `target_unit_id`, `allowed_model_ids`)
- fight_within_3_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="fight_within_3"`, `unit_id`, `target_unit_id`)
- possessed_lord_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="possessed_lord"`, `unit_id`, `model_id`)
- dance_of_death_dialog: CHOOSE_DANCE_OF_DEATH {choice} (context `unit_id`, `phase_name`, `ability_name`)
- adaptive_instincts_dialog: CHOOSE_ADAPTIVE_INSTINCTS {choice} (context `unit_id`, `phase_name`, `ability_name`)
- dread_mob_try_dat_button_fight_dialog: CHOOSE_QUARRY {button_mode, button_effect?} (context `ability="dread_mob_try_dat_button"`, `ability_name="Try Dat Button!"`, `army_id`, `unit_id`, `phase_name`, `trigger="fight"`, `candidate_button_modes[]`, `candidate_button_effects[]`, `optional=false`)
- harbinger_of_death_dialog: CHOOSE_HARBINGER_OF_DEATH {choice} (context `unit_id`, `model_id`, `weapon_name`, `ability_name`)
- channelled_force_dialog: CHOOSE_QUARRY {choice | skip} (context `ability="channelled_force"`, `ability_name="Channelled Force"`, `unit_id`, `phase="Fight phase"`, `candidate_choices[]`, `optional=true`)
- herald_of_ynnead_target_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="herald_of_ynnead"`, `attacker_unit_id`, `model_id`, `keyword`, `ability_name`)
- strength_from_death_lethal_reprisal_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="aeldari_strength_from_death_lethal_reprisal"`, `ability_name`, `turn`, `turn_owner_id`)
- strength_from_death_lethal_intent_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="aeldari_strength_from_death_lethal_intent"`, `ability_name`, `turn`, `turn_owner_id`, `optional=true`)
- fight_phase_target_attack_bonus_dialog: CHOOSE_QUARRY {target_unit_id} (context `ability="fight_phase_target_attack_bonus"`, `source_unit_id`, `model_id`, `range`, `keyword`, `attack_type`, `strength_bonus`, `ap_bonus`, `damage_bonus`, `wound_bonus`, `enemy_melee_wound_penalty`)
- inflamed_infections_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="inflamed_infections"`, `source_unit_id`, `attacker_unit_id`, `model_id`, `crit_hit_threshold`, `crit_hit_threshold_below_half`, `optional=true`)
- boon_of_death_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="boon_of_death"`, `source_unit_id`, `attacker_unit_id`, `turn`, `optional=true`)
- blinding_spray_dialog: CHOOSE_QUARRY {model_id | skip} (context `ability="blinding_spray"`, `ability_name`, `phase`, `optional=true`)
- malign_sacrifice_dialog: CHOOSE_QUARRY {target_unit_id, model_id | skip} (context `ability="malign_sacrifice"`, `source_unit_id`, `ability_name`)
- soulstain_made_manifest_dialog: CHOOSE_QUARRY {target_unit_id | skip} (context `ability="charge_end_select_one_battleshock"`, `ability_name="Soulstain Made Manifest"`, `source_unit_id`, `model_id`, `test_modifier=-1`, `optional=true`)
- fight_phase_melee_ap_boost_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="fight_phase_melee_ap_boost"`, `unit_id`, `model_id`)
- thrilling_spectacle_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="thrilling_spectacle"`, `unit_id`, `model_id`, `buff_key`, `invuln`, `attacks_value`)
- chance_for_glory_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="chance_for_glory"`, `unit_id`, `model_id`, `buff_key`, `bonus`)
- malefic_destruction_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="malefic_destruction"`, `unit_id`, `model_id`, `buff_key`, `weapon_name`, `attacks_bonus`)
- sacrificial_dagger_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="sacrificial_dagger"`, `unit_id`, `model_id`, `ability_name`, `phase`)
- sweeping_advance_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="sweeping_advance"`, `unit_id`, `model_id`, `ability_key`)
- daemonic_patrons_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="daemonic_patrons"`, `unit_id`)
- possessed_blade_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="possessed_blade_fight"`, `unit_id`, `model_id`, `weapon_name`)
- daemonic_patrons_loss_dialog: ALLOCATE_DAMAGE {model_id} (context `selection_kind="daemonic_patrons_loss"`, `unit_id`, `ability_name`)
- malefic_surge_diabolic_power_fight_dialog: CHOOSE_MALEFIC_SURGE_ABILITY {choice | skip} (context `ability="malefic_surge"`, `unit_id`, `trigger="fight"`)
- malefic_surge_unnatural_fortitude_fight_dialog: CHOOSE_MALEFIC_SURGE_ABILITY {choice | skip} (context `ability="malefic_surge"`, `unit_id`, `trigger="targeted_fight"`)
- hysterical_frenzy_psyker_dialog: CHOOSE_HYSTERICAL_FRENZY_PSYKER {model_id | skip} (context `target_unit_id`, `ability_name`, `phase`, `range`, `source_unit_id`)
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
- enhancement_charge_after_advance_once_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="enhancement_charge_after_advance_once"`, `unit_id`)
- advance_redeploy_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="advance_redeploy"`, `unit_id`, `min_enemy_distance_horiz`)
- opponent_turn_strategic_reserves_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="opponent_turn_strategic_reserves"`, `unit_id`)
- putrid_carapace_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="putrid_carapace"`, `unit_id`)
- leechbite_plate_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="leechbite_plate"`, `unit_id`, `model_id`, `pain_token_cost`)
- fight_phase_destroyed_strategic_reserves_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="fight_phase_destroyed_strategic_reserves"`, `unit_id`)
- opponent_turn_destroyed_reposition_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="opponent_turn_destroyed_reposition"`, `unit_id`, `destroyed_unit_id`, `destroyed_position`, `placement_position`, `turn_owner_id`, `turn`)
- seductive_gambit_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="seductive_gambit"`, `unit_id`)
- sensational_performance_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="sensational_performance"`, `unit_id`)
- cult_ambush_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="cult_ambush"`, `unit_id`)
- battle_focus_flitting_shadows_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_flitting_shadows"`, `unit_id`)
- battle_focus_sudden_strike_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_sudden_strike"`, `unit_id`)
- battle_focus_fade_back_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="battle_focus_fade_back"`, `unit_id`)
- battle_focus_lethal_surge_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="aeldari_strength_from_death_lethal_surge"`, `unit_id`, `attacker_unit_id`, `turn`, `turn_owner_id`)
- our_time_is_nigh_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="our_time_is_nigh"`, `unit_id`, `turn`, `turn_owner_id`, `phase`)
- start_any_phase_damage_set_one_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="start_any_phase_damage_set_one"`, `unit_id`, `model_id`, `buff_key`)
- start_any_phase_fnp_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="start_any_phase_fnp"`, `unit_id`, `ability_key`)
- dark_ritual_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="dark_ritual"`, `unit_id`, `ability_key`)
- desperate_devotion_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="desperate_devotion"`, `unit_id`, `trigger_action`, `turn`, `turn_owner_id`, `phase`)
- sentinel_storm_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="sentinel_storm"`, `unit_id`, `ability_key`)
- daemonic_ordnance_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="daemonic_ordnance"`, `unit_id`)
- warp_rift_firepower_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="warp_rift_firepower"`, `unit_id`, `ability_key`)
- warpmeld_sacrifice_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="warpmeld_sacrifice"`, `unit_id`, `ability_mode`, `trigger_action`, `source_unit_id`, `turn`, `turn_owner_id`)
- oathbound_speculator_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="oathbound_speculator"`, `unit_id`, `source_unit_id`, `cost`, `trigger`, `turn_owner`, `turn`)
- dead_reckoning_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="dead_reckoning"`, `unit_id`, `source_unit_id`, `turn_owner`, `turn`)
- cabal_channel_warp_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="cabal_channel_warp"`)
- stratagem_cp_discount_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="direct_the_slaughter"` or `ability="targeted_stratagem_discount"` or `ability="gift_of_foresight"` or `ability="mirror_of_fates"` or `ability="ancestral_crest"` or `ability="master_of_the_pageant"` or `ability="opponent_stratagem_cp_increase"` or `ability="brutal_example_overwatch"` or `ability="beast_handler_heroic_intervention"`)
- flickering_reality_reroll_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="flickering_reality_reroll"`, `unit_id`, `base_roll`, `ability_name`, `phase_name`)
- pyrogenesis_flux_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="pyrogenesis_flux"`, `unit_id`, `base_strength_bonus`, `base_ap_bonus`, `flux_strength_bonus`, `flux_ap_bonus`, `ability_name`, `phase_name`)
- power_from_pain_stratagem_dialog (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="power_from_pain_stratagem"`)

Dice Rolls:
- dice_roll_dialog: REQUEST_DICE_ROLL {roll_id, action_id="roll"}
- REQUEST_DICE_ROLL context includes `roll_spec.roll_explanation` (schema_version=1) with:
  `condition` (kind/op/target/applies_to) and typed modifier contributors for `sum_modifier` and `target_modifier`.
- dice_roll_dialog (reroll): SELECT_DICE_REROLL {roll_id, action_id, selected_die_ids[]}
- damage_allocation_dialog: ALLOCATE_DAMAGE {unit_id, model_id} (context `selection_kind`, `allowed_model_ids`, `remaining_wounds`, `sequence_id`/`save_index` when tied to attack resolution)
  Selection kinds in use: `wound_allocation`, `hazardous`, `mortal_wound` (attack sequence), `unit_mortal_wound` (non-attack), `reverberating_summons_return`, `bodyguard_return`, `bodyguard_loss`, `daemonic_patrons_loss`, `choice_samples`.
- overwatch_shooter_dialog: SELECT_RISE_TO_CHALLENGE {unit_id | skip}

Faction / Detachment / Ability choices:
- blessings_of_khorne_dialog: CHOOSE_BLESSINGS {choices[]}
- blood_tithe_dialog: CHOOSE_BLOOD_TITHE {choice_id}
- cabal_of_sorcerers_dialog: CHOOSE_RITUALS {choices[]}
- code_chivalric_dialog: CHOOSE_CHIVALRIC_OATH {choice_id}
- daemonic_allegiance_dialog: CHOOSE_DAEMONIC_ALLEGIANCE {choice_id}
- dark_pacts_dialog: CHOOSE_DARK_PACT {choice_id} (selected option payload may include `empyric_wellspring_choice` for Cabal of Chaos and `invoke_contract` for Soulforged Warpack)
- doctrina_imperatives_dialog: CHOOSE_DOCTRINA {choice_id}
- combat_doctrines_dialog: CHOOSE_COMBAT_DOCTRINE {choice_id | skip} (Combat Doctrines / Mastered Doctrines; availability validated by engine)
- angelic_legacy_dialog: CHOOSE_ANGELIC_LEGACY {choice_id} (Angelic Inheritors; payload includes `choice_keys` with exactly two selected legacy abilities)
- grand_coven_dialog: CHOOSE_GRAND_COVEN {choice_id | skip}
- combat_drugs_dialog: CHOOSE_COMBAT_DRUGS {choice_id}
- hyper_adaptations_dialog: CHOOSE_HYPER_ADAPTATION {choice_id}
- synaptic_imperatives_dialog: CHOOSE_QUARRY {choice_key | skip} (context `ability="synaptic_imperatives"`, `ability_name="Synaptic Imperatives"`, `army_id`, `battle_round`, `allowed_choice_keys[]`, `optional=true`)
- frenzy_choice_dialog: CHOOSE_FRENZY_TARGET {target_unit_id}
- harbingers_of_dread_dialog: CHOOSE_HARBINGER {choice_id | skip} (context `army_id`, `battle_round`; Traitoris Lance bonus choice uses `ability="traitoris_paragons_of_terror_bonus"`, `ability_name="Paragons of Terror"`, `allowed_choice_keys[]`, `optional=true`)
- martial_katah_dialog: CHOOSE_MARTIAL_KATAH {choice_id}
- martial_katah_dialog: CHOOSE_TECHNOSORCEROUS_AUGMENTATION {choice_id} (context `unit_id`, `ability_name`, `phase_name`)
- moment_shackle_dialog: CHOOSE_MOMENT_SHACKLE {choice_id | skip} (context `unit_id`, `model_id`, `ability_key`, `ability_name`)
- gilded_champion_dialog: USE_GILDED_CHAMPION {action="use" | action="skip", model_id, ability_key}
- careen_choice_dialog: USE_CAREEN {choice="normal" | choice="fall_back" | action="skip", unit_id, model_id}
- miracle_dice_dialog: USE_MIRACLE_DIE {die_value | skip} (context `unit_id`, `roll_type`, `dice_count`, `die_faces`, `pool`, `needed`)
- nurgles_gift_plague_dialog: CHOOSE_PLAGUE {choice_id | skip} (context `ability="nurgles_gift_declare"` or `ability="manifold_maladies"`, optional `battle_round`)
- pledge_selection_dialog: CHOOSE_PLEDGE {choice_id} (context `army_id`, `battle_round`, `max_value`, `ability_name="Pledges to the Dark Prince"`)
- quarry_selection_dialog: CHOOSE_QUARRY {target_unit_id | objective_id | mode | selected_unit_ids[] | skip} (context may include `ability`, `ability_name`, `effect_key`, `source_unit_id`, `prey_reroll_hit`, `prey_reroll_wound`, `prey_melee_only`, `prey_keyword`, `prey_repick_on_destroyed`, `source_model_id`, `singular_purpose_reroll_hit`, `singular_purpose_reroll_wound`, `singular_purpose_objective_fnp`, `singular_purpose_objective_oc`)
- quarry_selection_dialog (Experimental Augmentations choice): CHOOSE_QUARRY {mode="manual"+choice_key | mode="random"+choice_key="ROLL"} (context `ability="experimental_augmentations_choice"`, `ability_name="Experimental Augmentations"`, `army_id`, `battle_round`, `available_choice_keys[]`)
- quarry_selection_dialog (Experimental Augmentations reroll): CHOOSE_QUARRY {reroll_mode} (context `ability="experimental_augmentations_reroll"`, `ability_name="Experimental Augmentations"`, `army_id`, `battle_round`, `initial_rolls[]`, `available_reroll_modes[]`)
- quarry_selection_dialog (Vendetta): CHOOSE_QUARRY {target_unit_id} (context `ability="renegade_warband_vendetta_target"`, `ability_name="Vendetta"`, `army_id`, `battle_round`, `candidate_unit_ids[]`)
- quarry_selection_dialog (Focus of Hatred): CHOOSE_QUARRY {target_unit_id} (context `ability="veterans_of_the_long_war_focus_of_hatred_target"`, `ability_name="Focus of Hatred"`, `army_id`, `battle_round`, `candidate_unit_ids[]`)
- quarry_selection_dialog (Twisted Doctrine): CHOOSE_QUARRY {choice_key | skip} (context `ability="renegade_warband_twisted_doctrine"`, `ability_name="Twisted Doctrine"`, `unit_id`, `trigger_action`, `set_up_as_reinforcements`, `turn`, `turn_owner_id`, `allowed_choice_keys[]`)
- quarry_selection_dialog (Harbinger of Despair): CHOOSE_QUARRY {target_unit_id | skip} (context `ability="harbinger_of_despair_battleshock"`, `ability_name`, `ability_key`, `phase_name`, `unit_id`, `model_id`, `range`, `test_penalty`, `candidate_unit_ids[]`, `optional=true`, `once_per_turn=true`, `turn`)
- quarry_selection_dialog (Fight phase Engagement Battle-shock): CHOOSE_QUARRY {target_unit_id | skip} (context `ability="fight_phase_select_engagement_battleshock"`, `ability_name`, `ability_key`, `phase_name="FIGHT_PHASE"`, `unit_id`, `model_id`, `engagement_only=true`, optional `test_penalty`, `candidate_unit_ids[]`, `optional`, `once_per_turn`, `turn`)
- quarry_selection_dialog (Fight phase enemy melee hit penalty): CHOOSE_QUARRY {target_unit_id | skip} (context `ability="fight_phase_select_enemy_melee_hit_penalty"`, `ability_name`, `ability_key`, `phase_name="FIGHT_PHASE"`, `unit_id`, `source_unit_id`, `model_id`, `engagement_only=true`, `hit_penalty`, `candidate_unit_ids[]`, `optional`, `once_per_turn`, `turn`)
- quarry_selection_dialog (Huntress' Eye): CHOOSE_QUARRY {target_unit_id} (context `ability="huntress_eye"`, `ability_name="Huntress' Eye"`, `army_id`, `command_phase_owner_id`, `source_unit_id`, `source_member_unit_id`, `source_model_id`, `range`)
- quarry_selection_dialog (Veteran of the Kataphraktoi): CHOOSE_QUARRY {target_unit_id | skip} (context `ability="veteran_of_the_kataphraktoi"`, `ability_name="Veteran of the Kataphraktoi"`, `army_id`, `command_phase_owner_id`, `source_unit_id`, `source_member_unit_id`, `source_model_id`, `range`, `optional=true`)
- quarry_selection_dialog (Divine Aspect): CHOOSE_QUARRY {target_unit_id | skip} (context `ability="divine_aspect_target"`, `ability_name="Divine Aspect"`, `army_id`, `source_unit_id`, `source_model_id`, `range_inches=12`, `candidate_unit_ids[]`, `phase="Movement phase"`, `optional=true`)
- quarry_selection_dialog (Artillery Support mode): CHOOSE_QUARRY {artillery_support_mode} (context `ability="siege_regiment_artillery_support_mode"`, `ability_name="Artillery Support"`, `army_id`, `battle_round`, `allowed_modes[]`, `max_units`)
- realm_of_chaos_units_dialog (Artillery Support selections): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="siege_regiment_incendiary_bombardment"` or `ability="siege_regiment_smoke_shells"` or `ability="siege_regiment_creeping_barrage_selection"`, `ability_name`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`, optional `required_units`)
- realm_of_chaos_units_dialog (Houndpack Lance CHARACTER selection): SELECT_REALM_OF_CHAOS_UNITS {unit_ids} (context `ability="houndpack_lance_character_selection"`, `ability_name="Marked Prey"`, `phase="Muster Armies step"`, `army_id`, `allowed_unit_ids[]`, `max_units=3`, `required_units=3`)
- realm_of_chaos_units_dialog (Iconoclast Pave the Way selection): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="iconoclast_pave_the_way_selection"`, `ability_name="Pave the Way"`, `phase="Declare Battle Formations step"`, `army_id`, `allowed_unit_ids[]`, `max_units=3`, `optional=true`)
- realm_of_chaos_units_dialog (Masters of Misdirection selection): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="deceptors_masters_of_misdirection_selection"`, `ability_name="Masters of Misdirection"`, `phase="Declare Battle Formations step"`, `army_id`, `allowed_unit_ids[]`, `max_units`, `max_units_per_type`)
- realm_of_chaos_units_dialog (Informant Network selection): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="informant_network_selection"`, `ability_name="Informant Network"`, `phase="Declare Battle Formations step"`, `army_id`, `allowed_unit_ids[]`, `max_units=3`, `optional=true`)
- realm_of_chaos_units_dialog (Miasmic Bombardment selection): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `ability="miasmic_bombardment"`, `ability_name="Miasmic Bombardment"`, `army_id`, `battle_round`, `allowed_unit_ids[]`, `max_units`)
- realm_of_chaos_units_dialog (Glimmershift Portal): SELECT_REALM_OF_CHAOS_UNITS {unit_ids | skip} (context `max_units`, `allowed_unit_ids[]`) used at end of opponent Fight phase to choose up to two SCINTILLATING LEGIONS non-MONSTER units, or one SCINTILLATING LEGIONS MONSTER unit, that are each more than 6" horizontally from enemies
- quarry_selection_dialog (Iconoclast Dark Sacrifice): CHOOSE_QUARRY {damned_unit_id + sacrifice_mode | skip} (context `ability="iconoclast_dark_sacrifice"`, `ability_name="Dark Sacrifice"`, `source_unit_id`, `trigger="shooting"|"fight"`, `candidate_damned_unit_ids[]`, `allowed_modes[]`, `optional=true`)
- quarry_selection_dialog (Tyrant's Shadow): CHOOSE_QUARRY {objective_id} (context `ability="traitoris_tyrants_shadow_objective"`, `ability_name="Tyrant's Shadow"`, `army_id`, `battle_round`, `source_unit_id`, `candidate_objective_ids[]`, `optional=false`)
- quarry_selection_dialog (Malevolent Heraldry): CHOOSE_QUARRY {reroll_mode} (context `ability="traitoris_malevolent_heraldry"`, `ability_name="Malevolent Heraldry"`, `army_id`, `battle_round`, `source_unit_id`, `initial_rolls[]`, `available_reroll_modes[]`, `optional=false`)
- quarry_selection_dialog (Shadow Assignment): SHADOW_ASSIGNMENT {unit_id, replacement_datasheet_id | skip} (context `ability="shadow_assignment"`, `ability_name="Shadow Assignment"`)
- quarry_selection_dialog (Risen Rubricae): CHOOSE_QUARRY {selected_unit_ids[]} (context `ability="risen_rubricae"`, `ability_name="Risen Rubricae"`, `source_unit_id`, `enhancement_id`)
- quarry_selection_dialog (Ethereal Pathway): CHOOSE_QUARRY {selected_unit_ids[] | skip} (context `ability="ethereal_pathway"`, `ability_name="Ethereal Pathway"`, `source_unit_id`, `enhancement_id`)
- modifier_ignore_dialog: CHOOSE_HIT_MODIFIER_IGNORES {choice} (context `attacker_model_id`, `target_unit_id`, `wargear_id`, `profile_name`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_HIT_MODIFIER_IGNORES {choice} (context `attacker_model_id`, `target_unit_id`, `wargear_id`, `profile_name`, `ability_name`, `modifier_kind="wound_roll"`)
- modifier_ignore_dialog: CHOOSE_SKILL_MODIFIER_IGNORES {choice} (context `attacker_model_id`, `target_unit_id`, `wargear_id`, `profile_name`, `ability_name`, `modifier_kind="weapon_skill"`)
- modifier_ignore_dialog: CHOOSE_MOVE_MODIFIER_IGNORES {choice} (context `unit_id`, `action_type`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_ADVANCE_MODIFIER_IGNORES {choice} (context `unit_id`, `ability_name`)
- modifier_ignore_dialog: CHOOSE_CHARGE_MODIFIER_IGNORES {choice} (context `unit_id`, `target_unit_ids`, `ability_name`)
Note: modifier ignore dialogs are used by abilities like Driven by Ultimate Rage, Internal Rivalries, Siege Crawler, and Tears of the Phoenix. They are only requested when applicable modifiers exist, and their options are pruned to the relevant modifier signs.
- quarry_selection_dialog: CHOOSE_LIMB_FROM_LIMB {choice} (context `unit_id`)
- quarry_selection_dialog: CHOOSE_RED_WRATH {mode} (context `unit_id`)
- quarry_selection_dialog: CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE {zone | skip} (context `ability="impossible_eclipse"`, `unit_id`, `ability_name`)
- quarry_selection_dialog: PICK_OBJECTIVE {objective_id} (context `ability="a_grim_warning"` | `ability="corrupting_taint"` | `ability="corrupt_realspace"` | `ability="extinction_order"` | `ability="no_retreat"`)
- secondary_discard_dialog: DISCARD_SECONDARY {card_id}
- shadow_form_dialog: CHOOSE_SHADOW_FORM {choice_id}
- daemon_primarch_slaanesh_dialog: CHOOSE_DAEMON_PRIMARCH_SLAANESH {choice_id} (context `unit_id`, `opponent_player_id`, `battle_round`, `expires_round`)
- warmaster_dialog: CHOOSE_WARMASTER_ABILITY {choice_id} (context `unit_id`, `battle_round`, `player_id`, `expires_round`)
- templar_vows_dialog: CHOOSE_VOW {choice_id}
- voice_of_command_dialog: ISSUE_ORDER {unit_id, order_id}
- wrathful_presence_dialog: CHOOSE_WRATHFUL_PRESENCE {choice_id}
- yes_no_dialog: CONFIRM_YES_NO {choice}
- patrol_squad_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="patrol_squad"`, `unit_id`, `ability_name="Patrol Squad"`)
- extremis_level_threat_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context `ability="extremis_level_threat"`, `ability_name`, `army_id`)
- protector_of_paths_overwatch_prompt (yes_no_dialog): CONFIRM_YES_NO {choice} (context optional key `PROTECTOR_OF_PATHS_OVERWATCH`, `ability_name`, `stratagem`, `target_unit`, `base_cp_cost`)
- aspect_shrine_prompt_dialog: CHOOSE_ASPECT {choice_id}
- leading_unmodified_six_prompt_dialog: USE_LEADING_UNMODIFIED_SIX {ability_key | skip} (context `unit_id`, `attacker_model_id`, `roll_type`, `roll_value`, `ability_keys`)
- model_unmodified_six_prompt_dialog: USE_MODEL_UNMODIFIED_SIX {ability_key | skip} (context `unit_id`, `model_id`, `roll_type`, `roll_value`, `ability_keys`)
- example_dialog: CONFIRM_EXAMPLE {choice_id}
- reverberating_summons_unit_dialog: SELECT_REVERBERATING_SUMMONS_UNIT {unit_id | skip}
- reverberating_summons_return_model_dialog: ALLOCATE_DAMAGE {unit_id, model_id | skip} (context `selection_kind="reverberating_summons_return"`)
- choice_samples_dialog: ALLOCATE_DAMAGE {model_id | gain_cp | skip} (context `selection_kind="choice_samples"`, `unit_id`, `cp_gain`, `allowed_model_ids`)

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

### Presentation Envelope Contract

Canonical schema artifact: `src/warhammer40k_ai/engine/presentation_envelope.py`

Envelope fields:
- `schema_version` (major.minor; current major is authoritative)
- `stream_id` (deterministic per stream)
- `sequence_id` (monotonic per stream)
- `payload` (serialized update body)

Compatibility policy:
- major mismatch: fail-fast, request resync or reject payload.
- minor version changes: additive-only; consumers accept same-major updates.

Ordering/idempotency policy:
- duplicate `sequence_id` in a stream: ignore (idempotent apply).
- gap/out-of-order detection: trigger resync/rebuild path.
- reconnect/rehydration of presentation state uses `UI/presentation_state_hydrator.py`
  to rebuild `game_loaded` + pending decision surfaces from transcript order.

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
- `replay.sqlite3`: decision-indexed replay timeline (steps, event ranges, sparse keyframes) for step-by-step UI playback.
  SQLite runs in `DELETE` journal mode for this store so `replay.sqlite3` is a self-contained portable artifact.
  Format details: `docs/REPLAY_STORAGE_FORMAT.md`.

Cleanup:
- Manual only. No auto-pruning or expiry yet.
- Snapshot cadence: end of each phase (autosave).
- Event retention: keep only events since the most recent snapshot; flush on successful snapshot save.
- Runtime guardrail: deterministic event log keeps a bounded in-memory window (oldest-first pruning) to prevent unbounded growth during long sessions.
- Replay capture is independent of event-log trimming. Decision steps and linked events are persisted in `replay.sqlite3`.

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
