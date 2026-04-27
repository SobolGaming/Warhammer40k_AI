from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.selectable_section_abilities import (
    KEY_COUNTERSTRATEGIST,
    KEY_HERO_OF_HADES_HIVE,
    KEY_PULSE_JET,
    KEY_SHOKK_ATTACK_ENGINE,
    KEY_THROTTLEROKKIT_SHOKKA_ENGINE,
    KEY_TURBO_ENGINE,
    clear_active_section_ability,
    set_active_section_ability,
)
from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


def _ability(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description or name)


def _make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None, army=None):
    unit = Unit.__new__(Unit)
    unit._id = f"unit-{name.lower().replace(' ', '-')}"
    unit.name = name
    unit.parent_army = army
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = list(abilities or [])
    unit.models = []
    unit.round_state = SimpleNamespace()
    unit.can_be_attached_to = []
    unit.attached_to = None
    unit.attached_leaders = []
    unit.special_rules = {}
    unit._ability_cache = {}
    unit._ability_activity_generation = 0
    unit.deployed = True
    unit.embarked_in = None
    unit.reserve_status = "deployed"
    return unit


class _InitializedMockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Orks",
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [str(faction_name or "").upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "12",
                "T": "6",
                "Sv": "3",
                "W": "7",
                "Ld": "6",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": getattr(ability, "name", ""),
                "description": getattr(ability, "description", ""),
                "type": "Datasheet",
                "parameter": "",
            }
            for ability in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_initialized_unit(
    name: str,
    *,
    faction_name: str = "Orks",
    keywords=None,
    faction_keywords=None,
    abilities=None,
) -> Unit:
    unit = Unit(
        _InitializedMockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _wazdakka_abilities():
    return [
        _ability(
            "Throttlerokkit Shokka Engine",
            "In your Command phase, select one of the abilities in the Throttlerokkit Shokka Engine section.",
        ),
        _ability(
            "Turbo Engine",
            "This unit is eligible to declare a charge in a turn in which it Advanced or Fell Back.",
        ),
        _ability(
            "Shokk Attack Engine",
            "In your Command phase, if this unit is not within Engagement Range of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves.",
        ),
        _ability(
            "Pulse Jet",
            "Each time this unit Advances, do not make an Advance roll for it. Instead, until the end of the phase: Add 6\" to the Move characteristic of models in this unit. Models in this unit can move through models and terrain features.",
        ),
    ]


def _build_orks_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    ork_army = Army.with_detachment("Orks", detachment_type="War Horde")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ork_player, enemy_player, ork_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _pending_decision_by_ability(game: Game, ability: str):
    for request in list(game.decision_queue.list() or []):
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return request
    return None


def _option_by_payload(request: DecisionRequest, key: str, value):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if payload.get(key) == value:
            return option
    return None


def test_yarrick_section_sub_abilities_are_gated_by_command_choice():
    unit = _make_unit(
        "Commissar Yarrick",
        faction_keywords=["ASTRA MILITARUM"],
        abilities=[
            _ability(
                "Hero of Hades Hive",
                "In your Command phase, you can select one of the abilities in the Hero of Hades Hive section.",
            ),
            _ability(
                "Counterstrategist",
                "At the end of your opponent's Movement phase, you can select one enemy unit that was set up or ended a move within 12\" of this model's unit.",
            ),
        ],
    )

    assert not unit._ability_is_active("Counterstrategist")
    assert set_active_section_ability(unit, KEY_COUNTERSTRATEGIST, start_round=1, expires_round=2)
    assert unit._ability_is_active("Counterstrategist")

    clear_active_section_ability(unit, KEY_HERO_OF_HADES_HIVE)
    assert not unit._ability_is_active("Counterstrategist")


def test_wazdakka_section_sub_abilities_are_gated_by_command_choice():
    unit = _make_unit(
        "Wazdakka Gutsmek",
        keywords=["MOUNTED", "CHARACTER"],
        faction_keywords=["ORKS"],
        abilities=_wazdakka_abilities(),
    )

    assert not unit.has_advance_and_charge()
    assert unit._get_advance_no_roll_effect() is None
    assert not unit._ability_is_active("Shokk Attack Engine")

    assert set_active_section_ability(unit, KEY_TURBO_ENGINE, start_round=1, expires_round=2)
    assert unit.has_advance_and_charge()

    assert set_active_section_ability(unit, KEY_SHOKK_ATTACK_ENGINE, start_round=1, expires_round=2)
    assert unit._ability_is_active("Shokk Attack Engine")

    assert set_active_section_ability(unit, KEY_PULSE_JET, start_round=1, expires_round=2)
    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert effect["distance"] == 6
    assert "advance" in unit.special_rules.get("bearer_unit_phase_move_types", [])

    clear_active_section_ability(unit, KEY_THROTTLEROKKIT_SHOKKA_ENGINE)
    assert "advance" not in unit.special_rules.get("bearer_unit_phase_move_types", [])


def test_wazdakka_shokk_attack_engine_choice_queues_and_enters_strategic_reserves():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_orks_game()
    wazdakka = _make_initialized_unit(
        "Wazdakka Gutsmek",
        keywords=["MOUNTED", "VEHICLE", "CHARACTER"],
        faction_keywords=["ORKS"],
        abilities=_wazdakka_abilities(),
    )
    enemy = _make_initialized_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ork_army.add_unit(wazdakka)
    enemy_army.add_unit(enemy)
    _place_unit(game, wazdakka, 10.0, 10.0)
    _place_unit(game, enemy, 25.0, 10.0)
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="COMMAND_PHASE")
    game.phase = phase
    game.event_system.publish("phase_start", player=ork_player, phase=phase)
    selection_request = _pending_decision_by_ability(game, "selectable_section_ability")
    assert selection_request is not None
    option = _option_by_payload(selection_request, "choice_key", KEY_SHOKK_ATTACK_ENGINE)
    assert option is not None

    selected = resolve_decision_command(game, selection_request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(selected, "ok", False))

    shokk_request = _pending_decision_by_ability(game, "shokk_attack_engine_strategic_reserves")
    assert shokk_request is not None
    use_option = _option_by_payload(shokk_request, "action", "enter_strategic_reserves")
    assert use_option is not None

    applied = resolve_decision_command(game, shokk_request, use_option.option_id, player_id=ork_player.id)
    assert bool(getattr(applied, "ok", False))
    assert str(getattr(wazdakka, "reserve_status", "") or "").strip().lower() == "strategic_reserves"
    assert wazdakka not in game.map.units


def test_wazdakka_shokk_attack_engine_skip_leaves_unit_on_battlefield():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_orks_game()
    wazdakka = _make_initialized_unit(
        "Wazdakka Gutsmek",
        keywords=["MOUNTED", "VEHICLE", "CHARACTER"],
        faction_keywords=["ORKS"],
        abilities=_wazdakka_abilities(),
    )
    enemy = _make_initialized_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"])
    ork_army.add_unit(wazdakka)
    enemy_army.add_unit(enemy)
    _place_unit(game, wazdakka, 10.0, 10.0)
    _place_unit(game, enemy, 25.0, 10.0)
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="COMMAND_PHASE")
    game.phase = phase
    game.event_system.publish("phase_start", player=ork_player, phase=phase)
    selection_request = _pending_decision_by_ability(game, "selectable_section_ability")
    option = _option_by_payload(selection_request, "choice_key", KEY_SHOKK_ATTACK_ENGINE)
    selected = resolve_decision_command(game, selection_request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(selected, "ok", False))

    shokk_request = _pending_decision_by_ability(game, "shokk_attack_engine_strategic_reserves")
    skip_option = _option_by_payload(shokk_request, "action", "skip")
    assert skip_option is not None
    skipped = resolve_decision_command(game, shokk_request, skip_option.option_id, player_id=ork_player.id)
    assert bool(getattr(skipped, "ok", False))
    assert str(getattr(wazdakka, "reserve_status", "") or "").strip().lower() == "deployed"
    assert wazdakka in game.map.units


def test_wazdakka_shokk_attack_engine_is_blocked_while_engaged():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_orks_game()
    wazdakka = _make_initialized_unit(
        "Wazdakka Gutsmek",
        keywords=["MOUNTED", "VEHICLE", "CHARACTER"],
        faction_keywords=["ORKS"],
        abilities=_wazdakka_abilities(),
    )
    enemy = _make_initialized_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"])
    ork_army.add_unit(wazdakka)
    enemy_army.add_unit(enemy)
    _place_unit(game, wazdakka, 10.0, 10.0)
    _place_unit(game, enemy, 10.5, 10.0)
    game.rebuild_entity_registry()
    assert game.map.is_within_engagement_range(wazdakka, enemy)

    phase = SimpleNamespace(name="COMMAND_PHASE")
    game.phase = phase
    game.event_system.publish("phase_start", player=ork_player, phase=phase)
    selection_request = _pending_decision_by_ability(game, "selectable_section_ability")
    option = _option_by_payload(selection_request, "choice_key", KEY_SHOKK_ATTACK_ENGINE)
    selected = resolve_decision_command(game, selection_request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(selected, "ok", False))
    assert _pending_decision_by_ability(game, "shokk_attack_engine_strategic_reserves") is None

    manual_request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Shokk Attack Engine: place Wazdakka Gutsmek into Strategic Reserves?",
        player_id=ork_player.id,
        options=[
            DecisionOption.create(
                "Enter Strategic Reserves",
                payload={
                    "action": "enter_strategic_reserves",
                    "source_unit_id": wazdakka.id,
                    "unit_id": wazdakka.id,
                },
            ),
            DecisionOption.create(
                "None",
                payload={"skip": True, "action": "skip", "source_unit_id": wazdakka.id, "unit_id": wazdakka.id},
            ),
        ],
        context={
            "ability": "shokk_attack_engine_strategic_reserves",
            "ability_name": "Shokk Attack Engine",
            "source_unit_id": wazdakka.id,
            "unit_id": wazdakka.id,
            "battle_round": 1,
            "phase": "Command phase",
            "optional": True,
        },
    )
    game.request_decision(manual_request)
    use_option = _option_by_payload(manual_request, "action", "enter_strategic_reserves")
    rejected = resolve_decision_command(game, manual_request, use_option.option_id, player_id=ork_player.id)
    assert not bool(getattr(rejected, "ok", False))
    assert "Engagement Range" in " ".join(str(error) for error in getattr(rejected, "errors", ()) or ())
    assert str(getattr(wazdakka, "reserve_status", "") or "").strip().lower() == "deployed"


def test_support_matrix_classifies_wazdakka_shokk_attack_engine_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    shokk_status, shokk_notes = _classify_ability(
        "Shokk Attack Engine",
        "In your Command phase, if this unit is not within Engagement Range of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves.",
        faction_id="ORK",
        datasheet_id="000004221",
    )
    throttlerokkit_status, throttlerokkit_notes = _classify_ability(
        "Throttlerokkit Shokka Engine",
        "In your Command phase, select one of the abilities in the Throttlerokkit Shokka Engine section (see below). Until the start of your next Command phase, this model has that ability.",
        faction_id="ORK",
        datasheet_id="000004221",
    )

    assert shokk_status == "Supported"
    assert throttlerokkit_status == "Supported"
    assert "Strategic Reserves" in str(shokk_notes)
    assert "decision-routed" in str(throttlerokkit_notes)


def test_kroyle_on_my_signal_fire_parses_full_hit_reroll_for_two_keywords():
    unit = _make_unit(
        "Inquisitor Kroyle",
        abilities=[
            _ability(
                "On My Signal, Fire!",
                "After this unit has shot, you can select one enemy unit hit by those attacks. Until the end of the phase, each time an Agents of the Imperium or Imperium Infantry Battleline model from your army makes an attack that targets that enemy unit, you can re-roll the Hit roll.",
            )
        ],
    )

    specs = unit.unit_post_shoot_keyword_hit_reroll_ones_specs()
    assert len(specs) == 1
    assert specs[0]["source"] == "On My Signal, Fire!"
    assert specs[0]["reroll_full"] is True
    assert specs[0]["keyword_phrases_any"] == (
        "AGENTS OF THE IMPERIUM",
        "IMPERIUM INFANTRY BATTLELINE",
    )


def test_kroyle_tox_cycler_parses_permanent_self_weapon_bonus():
    model = SimpleNamespace(_id="kroyle-model", name="Inquisitor Kroyle", abilities={}, is_alive=True)
    unit = _make_unit(
        "Inquisitor Kroyle",
        abilities=[
            _ability(
                "Tox-cycler",
                "In your Shooting phase, after this unit has shot, if this model scored a hit with its Jindarii tox-cycler, until the end of the battle, add 2 to the Strength and Damage characteristics of that weapon (to a maximum Damage characteristic of 6).",
            )
        ],
    )
    unit.models = [model]
    model.parent_unit = unit

    assert unit.model_post_shoot_self_weapon_bonus_specs(model) == [
        {
            "source": "Tox-cycler",
            "weapon_key": "jindarii tox cycler",
            "weapon_name": "jindarii tox cycler",
            "strength_bonus": 2,
            "damage_bonus": 2,
            "max_damage": 6,
        }
    ]


def test_intranzia_judged_for_execution_parses_and_applies_attacker_keyword_gate():
    model = SimpleNamespace(_id="intranzia-model", name="Intranzia Fraye", abilities={}, is_alive=True)
    source = _make_unit(
        "Intranzia Fraye",
        faction_keywords=["ADEPTA SORORITAS"],
        abilities=[
            _ability(
                "Judged for Execution",
                "At the end of your Movement phase, you can select one enemy unit within 18\" of and visible to this model. Until the start of your next Command phase, each time a friendly ADEPTA SORORITAS model makes an attack that targets that enemy unit, that attack has the [LETHAL HITS] ability.",
            )
        ],
    )
    source.models = [model]
    model.parent_unit = source

    specs = source.model_movement_phase_end_visible_attack_keyword_specs(model)
    assert specs == [
        {
            "source": "Judged for Execution",
            "ability_key": "judged for execution",
            "range": 18,
            "attacker_keyword_phrase": "adepta sororitas",
            "attack_type": "any",
            "keywords": ["LETHAL HITS"],
            "expires_timing": "OWNER_NEXT_COMMAND_START",
        }
    ]

    target = _make_unit("Enemy")
    target.special_rules["selected_to_shoot_target_attack_keyword_effects"] = [
        {
            "source": "Judged for Execution",
            "owner_id": "",
            "turn": 0,
            "expires_phase": "",
            "attack_type": "any",
            "keywords": ["LETHAL HITS"],
            "attacker_keyword_phrase": "ADEPTA SORORITAS",
        }
    ]
    attacker_model = SimpleNamespace(_id="sister-model", name="Sister", abilities={}, is_alive=True)
    attacker = _make_unit("Battle Sisters", faction_keywords=["ADEPTA SORORITAS"])
    attacker.models = [attacker_model]
    attacker_model.parent_unit = attacker

    rules = attacker.get_attack_keyword_bonuses(
        attack_type="ranged",
        model=attacker_model,
        target=target,
    )
    assert rules["lethal_hits"] is True
    assert "Lethal Hits (Judged for Execution)" in rules["sources"]

    non_sororitas = _make_unit("Guardsmen", faction_keywords=["ASTRA MILITARUM"])
    non_sororitas_model = SimpleNamespace(_id="guardsman-model", name="Guardsman", abilities={}, is_alive=True)
    non_sororitas.models = [non_sororitas_model]
    non_sororitas_model.parent_unit = non_sororitas
    assert bool(non_sororitas.get_attack_keyword_bonuses(
        attack_type="ranged",
        model=non_sororitas_model,
        target=target,
    ).get("lethal_hits", False)) is False


def test_intranzia_righteous_denunciation_parses_fight_phase_aura_battleshock():
    model = SimpleNamespace(_id="intranzia-model", name="Intranzia Fraye", abilities={}, is_alive=True)
    source = _make_unit(
        "Intranzia Fraye",
        faction_keywords=["ADEPTA SORORITAS"],
        abilities=[
            _ability(
                "Righteous Denunciation",
                "At the start of the Fight phase, each enemy unit within 6\" of this model must take a Battle-shock test, subtracting 1 from that test.",
            )
        ],
    )
    source.models = [model]
    model.parent_unit = source

    specs = source.model_start_fight_phase_aura_battleshock_specs(model)
    assert specs == [
        {
            "source": "Righteous Denunciation",
            "range": 6,
            "required_keywords": [],
            "required_keyword_mode": "all",
            "exclude_keywords": [],
            "penalty": 1,
        }
    ]


def test_support_matrix_classifies_righteous_denunciation_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(
        "Righteous Denunciation",
        "At the start of the Fight phase, each enemy unit within 6\" of this model must take a Battle-shock test, subtracting 1 from that test.",
        faction_id="AS",
        datasheet_id="000004215",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "enemy units within 6" in notes_l
    assert "battle-shock test at -1" in notes_l


def test_commissar_graves_variants_are_mutually_exclusive():
    army = Army.with_detachment("Astra Militarum", detachment_type="Combined Arms")
    army.units = [
        _make_unit("Commissar Graves", army=army),
        _make_unit("Commissar Graves on Foot", army=army),
    ]

    with pytest.raises(ArmyValidationError, match="Commissar Graves / Commissar Graves on Foot"):
        army.validate_unique_model_restrictions()


def test_support_matrix_classifies_genestealer_cults_rapid_strike_vehicle_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(
        "Rapid Strike Vehicle",
        "While one or more units are embarked within this model, unless this model is Battle-shocked, add 1 to this model's Objective Control characteristic for every 3 models (rounding down) embarked within it.",
        faction_id="GC",
        datasheet_id="000004222",
    )

    assert status == "Supported"
    assert "Objective Control" in notes
    assert "full 3 embarked models" in notes


def test_centaur_rsv_objective_control_scales_with_embarked_model_count():
    transport = _make_unit(
        "Centaur RSV",
        abilities=[
            _ability(
                "Rapid Strike Vehicle",
                "While one or more units are embarked within this model, unless this model is Battle-shocked, add 1 to this model's Objective Control characteristic for every 3 models (rounding down) embarked within it.",
            )
        ],
    )
    transport.keywords.append("Transport")
    transport.models = [SimpleNamespace(objective_control=1, is_alive=True)]
    passenger = _make_unit("Infantry Squad")
    passenger.models = [SimpleNamespace(is_alive=True) for _ in range(7)]
    transport.transport_passengers = [passenger]
    transport.is_battle_shocked = lambda: False

    assert transport.rapid_strike_vehicle_objective_control_bonus() == (2, "Rapid Strike Vehicle")
    assert transport.objective_control == 3

    transport.is_battle_shocked = lambda: True
    assert transport.rapid_strike_vehicle_objective_control_bonus() == (0, "")
    assert transport.objective_control == 1


def test_embarked_model_objective_control_bonus_supports_legacy_transport_wording():
    transport = _make_unit(
        "Transport",
        abilities=[
            _ability(
                "Rapid Strike Vehicle",
                "While one or more units are embarked within this transport, unless this unit is Battle-shocked, add 1 to its Objective Control characteristic for every 3 models embarked within it.",
            )
        ],
    )
    transport.keywords.append("Transport")
    passenger = _make_unit("Infantry Squad")
    passenger.models = [SimpleNamespace(is_alive=True) for _ in range(6)]
    transport.transport_passengers = [passenger]
    transport.is_battle_shocked = lambda: False

    assert transport.rapid_strike_vehicle_objective_control_bonus() == (2, "Rapid Strike Vehicle")


def test_wazdakka_warlord_grants_warbikers_battleline():
    army = Army.with_detachment("Orks", detachment_type="War Horde")
    army.faction_id = "ORK"
    wazdakka = _make_unit(
        "Wazdakka Gutsmek",
        keywords=["CHARACTER"],
        faction_keywords=["ORKS"],
        army=army,
    )
    warbikers = _make_unit("Warbikers", keywords=["MOUNTED"], faction_keywords=["ORKS"], army=army)

    army.add_unit(wazdakka)
    army.add_unit(warbikers)
    army.select_warlord(wazdakka)

    assert "Battleline" in warbikers.keywords


def test_waha_helper_prefers_non_legendary_wolf_scouts_without_explicit_legendary_request():
    helper = WahaHelper.__new__(WahaHelper)
    helper.datasheets = {
        "legend": {"id": "legend", "name": "Wolf Scouts (Legendary)", "faction_id": "SM"},
        "latest": {"id": "latest", "name": "Wolf Scouts", "faction_id": "SM"},
    }

    assert helper.get_datasheet("Wolf Scouts").id == "latest"
    assert helper.get_datasheet("Wolf Scouts Legendary").id == "legend"


def test_rapid_embarkation_collision_does_not_mark_new_armoured_speartip_entry_implemented():
    manager = StratagemManager.__new__(StratagemManager)
    manager._defensive_reaction_cache = {}
    manager._charge_melee_ap_cache = {}
    manager._consolidate_move_cache = {}
    firestorm_army = Army.with_detachment("Space Marines", detachment_type="Firestorm Assault Force")
    firestorm_army.faction_id = "SM"
    manager.player = SimpleNamespace(get_army=lambda: firestorm_army)

    old_firestorm = Stratagem(
        id="000008483004",
        name="RAPID EMBARKATION",
        type="Strategic Ploy Stratagem",
        description="",
        cp_cost=1,
        turn="Opponent's turn",
        phase="Fight phase",
        detachment="Firestorm Assault Force",
        faction_id="SM",
    )
    new_armoured_speartip = Stratagem(
        id="000010780004",
        name="RAPID EMBARKATION",
        type="Strategic Ploy Stratagem",
        description="",
        cp_cost=1,
        turn="Opponent's turn",
        phase="Fight phase",
        detachment="Armoured Speartip",
        faction_id="SM",
    )

    assert manager._is_implemented_stratagem(old_firestorm) is True
    assert manager._is_implemented_stratagem(new_armoured_speartip) is False


def test_burst_of_speed_collision_entries_remain_separate_and_only_armoured_infantry_is_implemented():
    manager = StratagemManager.__new__(StratagemManager)
    manager._defensive_reaction_cache = {}
    manager._charge_melee_ap_cache = {}
    manager._consolidate_move_cache = {}
    manager.player = SimpleNamespace(get_army=lambda: None)

    challenger = Stratagem(
        id="000010247002",
        name="BURST OF SPEED",
        type="Challenger - Strategic Ploy Stratagem",
        description="<b>WHEN:</b> End of your Shooting phase.",
        cp_cost=0,
        turn="Your turn",
        phase="Shooting phase",
        detachment="",
        faction_id="",
    )
    armoured_infantry = Stratagem(
        id="000010792004",
        name="BURST OF SPEED",
        type="Armoured Infantry - Strategic Ploy Stratagem",
        description="<b>WHEN:</b> End of your Movement phase.",
        cp_cost=1,
        turn="Your turn",
        phase="Movement phase",
        detachment="Armoured Infantry",
        faction_id="AM",
    )

    assert challenger.id != armoured_infantry.id
    assert manager._is_implemented_stratagem(challenger) is False
    assert manager._is_implemented_stratagem(armoured_infantry) is True


def test_armour_of_contempt_uses_deathwatch_target_constraint_when_text_requires_it():
    deathwatch_aoc = Stratagem(
        id="000009127002",
        name="ARMOUR OF CONTEMPT",
        type="Battle Tactic Stratagem",
        description=(
            "<b>TARGET:</b> One DEATHwATCH unit from your army that was selected as the target "
            "of one or more of the attacking unit's attacks."
        ),
        cp_cost=1,
        turn="Either player's turn",
        phase="Shooting or Fight phase",
        detachment="Ordo Xenos Alien Hunters",
        faction_id="AoI",
    )
    regular_aoc = Stratagem(
        id="000010780003",
        name="ARMOUR OF CONTEMPT",
        type="Battle Tactic Stratagem",
        description="<b>TARGET:</b> One ADEPTUS ASTARTES unit from your army.",
        cp_cost=1,
        turn="Either player's turn",
        phase="Shooting or Fight phase",
        detachment="Armoured Speartip",
        faction_id="SM",
    )

    assert StratagemManager._armour_of_contempt_target_keywords(deathwatch_aoc) == ("DEATHWATCH",)
    assert StratagemManager._armour_of_contempt_target_keywords(regular_aoc) == ("ADEPTUS ASTARTES",)
