from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        move: int = 6,
        wounds: int = 2,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None, wounds: int = 2) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _set_location(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (0.1 * index), float(y), 0.0, 0.0)


def _first_yes_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        if bool((option.payload or {}).get("choice", False)):
            return option.option_id
    raise AssertionError("No yes option found.")


def _target_option_id(request, target_unit: Unit) -> str:
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(option.payload or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option.option_id
    raise AssertionError(f"No target option found for {target_unit.name}.")


def test_intercessor_target_elimination_requires_single_target_and_boosts_bolt_rifles():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    intercessors = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    enemy_one = _mock_unit("Enemy One", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_two = _mock_unit("Enemy Two", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy_one)
    enemy_army.add_unit(enemy_two)
    _register_units(game, intercessors, enemy_one, enemy_two)

    bolt_rifle_model = next(
        model for model in list(intercessors.models or []) if any(getattr(wg, "name", "") == "Bolt rifle" for wg in list(model.wargear or []))
    )
    bolt_rifle = next(wg for wg in list(bolt_rifle_model.wargear or []) if getattr(wg, "name", "") == "Bolt rifle")
    baseline_attacks = int(bolt_rifle.profiles["default"].preview_attack_count(enemy_one, bolt_rifle_model).num_attacks)

    game._on_shooting_targets_selected_selected_to_shoot_unit_named_ranged_bonus(
        attacking_unit=intercessors,
        target_units=[enemy_one, enemy_two],
    )
    assert list(game.decision_queue.list() or []) == []

    game._on_shooting_targets_selected_selected_to_shoot_unit_named_ranged_bonus(
        attacking_unit=intercessors,
        target_units=[enemy_one],
    )
    requests = list(game.decision_queue.list() or [])
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO

    resolve_decision_command(game, request, _first_yes_option_id(request), player_id=sm_player.id)

    boosted_attacks = int(bolt_rifle.profiles["default"].preview_attack_count(enemy_one, bolt_rifle_model).num_attacks)
    assert boosted_attacks == baseline_attacks + 2


def test_invader_atv_outrider_escort_queues_reactive_shooting():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    game.current_player_index = 1

    enemy_attacker = _mock_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    mounted_target = _mock_unit("Mounted Squad", keywords=["MOUNTED"], faction_keywords=["ADEPTUS ASTARTES"])
    invader_atv = _actual_unit("Invader ATV", datasheet_id="000001158")

    enemy_army.add_unit(enemy_attacker)
    sm_army.add_unit(mounted_target)
    sm_army.add_unit(invader_atv)
    _set_location(enemy_attacker, 0.0, 0.0)
    _set_location(mounted_target, 5.0, 0.0)
    _set_location(invader_atv, 8.0, 0.0)
    _register_units(game, enemy_attacker, mounted_target, invader_atv)

    rule = invader_atv.get_guns_blazing_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Outrider Escort"
    assert str(rule.get("friendly_keyword", "") or "") == "ADEPTUS ASTARTES MOUNTED"
    assert int(rule.get("range", 0) or 0) == 6

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_attacker, target_units=[mounted_target])
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy_attacker, hits_by_target={mounted_target: 1})

    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert request.decision_type == DECISION_DECLARE_SHOTS
    assert bool((request.context or {}).get("guns_blazing_flow", False)) is True
    assert str((request.context or {}).get("guns_blazing_source", "") or "") == "Outrider Escort"
    assert str((request.context or {}).get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")


def test_invictor_combat_support_queues_reactive_shooting():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    game.current_player_index = 1

    enemy_attacker = _mock_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    phobos_target = _mock_unit(
        "Phobos Squad",
        keywords=["PHOBOS", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    invictor = _actual_unit("Invictor Tactical Warsuit", datasheet_id="000001156")

    enemy_army.add_unit(enemy_attacker)
    sm_army.add_unit(phobos_target)
    sm_army.add_unit(invictor)
    _set_location(enemy_attacker, 0.0, 0.0)
    _set_location(phobos_target, 5.0, 0.0)
    _set_location(invictor, 8.0, 0.0)
    _register_units(game, enemy_attacker, phobos_target, invictor)

    rule = invictor.get_guns_blazing_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Combat Support"
    assert str(rule.get("friendly_keyword", "") or "") == "ADEPTUS ASTARTES PHOBOS INFANTRY"
    assert int(rule.get("range", 0) or 0) == 6

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_attacker, target_units=[phobos_target])
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy_attacker, hits_by_target={phobos_target: 1})

    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert request.decision_type == DECISION_DECLARE_SHOTS
    assert bool((request.context or {}).get("guns_blazing_flow", False)) is True
    assert str((request.context or {}).get("guns_blazing_source", "") or "") == "Combat Support"
    assert str((request.context or {}).get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")


def test_iron_father_feirros_master_of_the_forge_repairs_and_buffs_vehicle():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    feirros = _actual_unit("Iron Father Feirros", datasheet_id="000000127")
    vehicle = _mock_unit("Vehicle", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"], wounds=10)
    vehicle_model = vehicle.models[0]
    vehicle_model._base_wounds = 10
    vehicle_model._wounds = 4

    sm_army.add_unit(feirros)
    sm_army.add_unit(vehicle)
    _set_location(feirros, 0.0, 0.0)
    _set_location(vehicle, 2.0, 0.0)
    _register_units(game, feirros, vehicle)

    rule = feirros.get_command_phase_vehicle_repair_hit_bonus_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Master of the Forge"
    assert int(rule.get("heal_flat", 0) or 0) == 3
    assert int(rule.get("hit_bonus", 0) or 0) == 1

    game._on_phase_start_master_of_mechanisms(player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_QUARRY

    resolve_decision_command(game, request, _target_option_id(request, vehicle), player_id=sm_player.id)

    assert int(vehicle_model.wounds) == 7
    sr = getattr(vehicle, "special_rules", {}) or {}
    assert bool(sr.get("master_of_mechanisms_hit_bonus_active")) is True
    assert int(sr.get("master_of_mechanisms_hit_bonus", 0) or 0) == 1
