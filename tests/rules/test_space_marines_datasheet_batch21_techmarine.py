from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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
                "M": "6",
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


def _target_option_id(request, target_unit: Unit) -> str:
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(option.payload or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option.option_id
    raise AssertionError(f"No target option found for {target_unit.name}.")


def test_techmarine_blessing_of_the_omnissiah_repairs_and_buffs_vehicle():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    techmarine = _actual_unit("Techmarine", datasheet_id="000000140")
    vehicle = _mock_unit("Vehicle", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"], wounds=10)
    vehicle_model = vehicle.models[0]
    vehicle_model._base_wounds = 10
    vehicle_model._wounds = 5

    sm_army.add_unit(techmarine)
    sm_army.add_unit(vehicle)
    _set_location(techmarine, 0.0, 0.0)
    _set_location(vehicle, 2.0, 0.0)
    _register_units(game, techmarine, vehicle)
    enemy_army.units = []

    rule = techmarine.get_command_phase_vehicle_repair_hit_bonus_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Blessing of the Omnissiah"
    assert str(rule.get("heal_roll", "") or "") == "D3"
    assert int(rule.get("hit_bonus", 0) or 0) == 1

    game._on_phase_start_master_of_mechanisms(player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_QUARRY

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        resolve_decision_command(game, request, _target_option_id(request, vehicle), player_id=sm_player.id)

    assert int(vehicle_model.wounds) == 7
    sr = getattr(vehicle, "special_rules", {}) or {}
    assert bool(sr.get("master_of_mechanisms_hit_bonus_active")) is True
    assert int(sr.get("master_of_mechanisms_hit_bonus", 0) or 0) == 1
