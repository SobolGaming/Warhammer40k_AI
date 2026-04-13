from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_handlers.abilities import _validate_choose_quarry
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


ROD_OF_THE_WAR_FORGE_TEXT = (
    "In your Command phase, select one of the abilities in the Icon of War section. Until the start of your next "
    "Command phase, this model has that ability."
)
FANATICAL_DEVOTION_TEXT = (
    "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
    "Command phase, that unit is eligible to shoot and declare a charge in a turn in which it Advanced."
)
ADAPTIVE_TACTICS_TEXT = (
    "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
    "Command phase, that unit is eligible to shoot and declare a charge in a turn in which it Fell Back."
)
THE_FIRES_OF_MARS_TEXT = (
    "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
    "Command phase, the Conqueror Imperative and Protector Imperative are both active for that unit."
)
MECHANICUS_BODYGUARD_TEXT = (
    "While this model is within 3\" of one or more other friendly ADEPTUS MECHANICUS units, this model has the Lone Operative ability."
)
CYBERNETIC_AUGMENTATION_TEXT = (
    "This model can move through terrain features, but cannot end a move within a wall, a floor, etc. This model can be "
    "set up or end a move on any floor level of RUINS, but if that level is not the ground floor, it can only do so if its "
    "base does not overhang the floor at that level."
)
SECUTOR_OF_OLYMPUS_TEXT = (
    "At the start of your Shooting phase, select one enemy VEHICLE unit within 12\" of this model and roll one D6: "
    "on a 2+, that enemy unit suffers D3+1 mortal wounds."
)
DOCTRINA_IMPERATIVES_TEXT = "Doctrina Imperatives."


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Other")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.turn = 1
    return game, admech_army, enemy_army, p1, p2


def _find_quarry_request(game: Game, ability_key: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == str(ability_key)
        ),
        None,
    )


def _option_with_payload(request, key: str, value: str):
    return next(
        (
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get(key, "")) == str(value)
        ),
        None,
    )


def _thulia_abilities():
    return [
        _make_ability("Rod of the War Forge", ROD_OF_THE_WAR_FORGE_TEXT),
        _make_ability("Fanatical Devotion", FANATICAL_DEVOTION_TEXT),
        _make_ability("Adaptive Tactics", ADAPTIVE_TACTICS_TEXT),
        _make_ability("The Fires of Mars", THE_FIRES_OF_MARS_TEXT),
        _make_ability("Mechanicus Bodyguard", MECHANICUS_BODYGUARD_TEXT),
        _make_ability("Cybernetic Augmentation", CYBERNETIC_AUGMENTATION_TEXT),
        _make_ability("Secutor of Olympus", SECUTOR_OF_OLYMPUS_TEXT),
    ]


def test_fanatical_devotion_grants_advance_shoot_and_charge_until_next_command_phase():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=_thulia_abilities(),
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_unit = _make_unit(
        "Far Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(skitarii)
    admech_army.add_unit(far_unit)
    game.map.units = [thulia, skitarii, far_unit]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    skitarii.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    far_unit.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "thulia_ghuld_rod_of_the_war_forge")
    assert mode_request is not None
    mode_option = _option_with_payload(mode_request, "rod_of_the_war_forge_mode", "fanatical_devotion")
    assert mode_option is not None
    mode_result = resolve_decision_command(game, mode_request, mode_option.option_id, player_id=p1.id)
    assert bool(getattr(mode_result, "ok", False)) is True

    target_request = _find_quarry_request(game, "thulia_ghuld_icon_of_war_target")
    assert target_request is not None
    skitarii_id = str(get_entity_id(skitarii) or "")
    target_option = _option_with_payload(target_request, "target_unit_id", skitarii_id)
    assert target_option is not None
    target_result = resolve_decision_command(game, target_request, target_option.option_id, player_id=p1.id)
    assert bool(getattr(target_result, "ok", False)) is True

    assert skitarii.has_advance_and_shoot() is True
    assert skitarii.has_advance_and_charge() is True
    assert far_unit.has_advance_and_shoot() is False
    assert far_unit.has_advance_and_charge() is False

    game.turn = 2
    game._on_phase_start_thulia_ghuld_rod_of_the_war_forge(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    assert skitarii.has_advance_and_shoot() is False
    assert skitarii.has_advance_and_charge() is False


def test_adaptive_tactics_grants_fall_back_shoot_and_charge():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=_thulia_abilities(),
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(skitarii)
    game.map.units = [thulia, skitarii]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    skitarii.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "thulia_ghuld_rod_of_the_war_forge")
    mode_option = _option_with_payload(mode_request, "rod_of_the_war_forge_mode", "adaptive_tactics")
    mode_result = resolve_decision_command(game, mode_request, mode_option.option_id, player_id=p1.id)
    assert bool(getattr(mode_result, "ok", False)) is True

    target_request = _find_quarry_request(game, "thulia_ghuld_icon_of_war_target")
    target_option = _option_with_payload(target_request, "target_unit_id", str(get_entity_id(skitarii) or ""))
    target_result = resolve_decision_command(game, target_request, target_option.option_id, player_id=p1.id)
    assert bool(getattr(target_result, "ok", False)) is True

    assert skitarii.has_fell_back_and_shoot() is True
    assert skitarii.can_charge_after_fall_back() is True


def test_the_fires_of_mars_grants_both_doctrina_keys_to_target_unit():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=_thulia_abilities(),
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Skitarii Vanguard",
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    other = _make_unit(
        "Other Vanguard",
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(target)
    admech_army.add_unit(other)
    game.map.units = [thulia, target, other]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    other.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    doctrina_mgr = admech_army.doctrina_imperatives
    assert doctrina_mgr.select_imperative("PROTECTOR", battle_round=1)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "thulia_ghuld_rod_of_the_war_forge")
    mode_option = _option_with_payload(mode_request, "rod_of_the_war_forge_mode", "the_fires_of_mars")
    assert mode_option is not None
    assert bool(resolve_decision_command(game, mode_request, mode_option.option_id, player_id=p1.id).ok) is True

    target_request = _find_quarry_request(game, "thulia_ghuld_icon_of_war_target")
    target_option = _option_with_payload(target_request, "target_unit_id", str(get_entity_id(target) or ""))
    assert target_option is not None
    assert bool(resolve_decision_command(game, target_request, target_option.option_id, player_id=p1.id).ok) is True

    assert doctrina_mgr.get_active_imperative_keys_for_unit(target, game=game) == {"PROTECTOR", "CONQUEROR"}
    assert doctrina_mgr.get_active_imperative_keys_for_unit(other, game=game) == {"PROTECTOR"}


def test_icon_of_war_target_validation_rejects_non_candidate_selection():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=_thulia_abilities(),
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_unit = _make_unit(
        "Far Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(skitarii)
    admech_army.add_unit(far_unit)
    game.map.units = [thulia, skitarii, far_unit]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    skitarii.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    far_unit.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "thulia_ghuld_rod_of_the_war_forge")
    mode_option = _option_with_payload(mode_request, "rod_of_the_war_forge_mode", "fanatical_devotion")
    assert bool(resolve_decision_command(game, mode_request, mode_option.option_id, player_id=p1.id).ok) is True

    target_request = _find_quarry_request(game, "thulia_ghuld_icon_of_war_target")
    assert target_request is not None
    invalid_option = DecisionOption.create(
        "Far Rangers",
        payload={"target_unit_id": str(get_entity_id(far_unit) or "")},
    )
    target_request.options.append(invalid_option)
    invalid_result = DecisionResult(
        decision_id=target_request.decision_id,
        player_id=p1.id,
        option_id=invalid_option.option_id,
        payload={"target_unit_id": str(get_entity_id(far_unit) or "")},
    )
    errors = tuple(_validate_choose_quarry(game, target_request, invalid_result))
    assert errors == ("Selected action_id is not present in candidates.",)


def test_secutor_of_olympus_queues_vehicle_target_without_visibility_and_deals_d3_plus_1_mortals():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=[_make_ability("Secutor of Olympus", SECUTOR_OF_OLYMPUS_TEXT)],
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(thulia)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [thulia, enemy_vehicle]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_vehicle.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    thulia._has_line_of_sight_to_target = lambda *_args, **_kwargs: False
    thulia._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_quarry_request(game, "thulia_ghuld_secutor_of_olympus")
    assert request is not None
    target_option = _option_with_payload(request, "target_unit_id", str(get_entity_id(enemy_vehicle) or ""))
    assert target_option is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2, 2]):
        result = resolve_decision_command(game, request, target_option.option_id, player_id=p1.id)

    assert bool(getattr(result, "ok", False)) is True
    thulia._apply_mortal_wounds_to_unit.assert_called_once()
    call_args = thulia._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is enemy_vehicle
    assert int(call_args.args[1]) == 3


def test_cybernetic_augmentation_grants_terrain_passthrough_and_ruins_access():
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=[_make_ability("Cybernetic Augmentation", CYBERNETIC_AUGMENTATION_TEXT)],
        keywords=["CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    assert thulia.can_move_through_ruins_walls() is True
    assert thulia.can_access_upper_floors() is True
    assert thulia.can_overhang_floor() is False

    move_profile = build_movement_profile(thulia, MovementType.MOVE)
    advance_profile = build_movement_profile(thulia, MovementType.ADVANCE)
    fall_back_profile = build_movement_profile(thulia, MovementType.FALL_BACK)

    assert move_profile.can_move_through_terrain is True
    assert advance_profile.can_move_through_terrain is True
    assert fall_back_profile.can_move_through_terrain is True
    assert move_profile.can_breach_ruins_walls is True
    assert move_profile.can_end_on_upper_surfaces is True


def test_mechanicus_bodyguard_grants_lone_operative_near_other_admech_units():
    game, admech_army, _enemy_army, _p1, _p2 = _build_game()
    thulia = _make_unit(
        "Thulia Ghuld",
        abilities=[_make_ability("Mechanicus Bodyguard", MECHANICUS_BODYGUARD_TEXT)],
        keywords=["CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    nearby = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(nearby)
    game.map.units = [thulia, nearby]
    game.rebuild_entity_registry()

    thulia.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    nearby.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    assert thulia.has_lone_operative() is True
