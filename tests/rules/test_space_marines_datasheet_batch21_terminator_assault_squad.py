from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float):
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None) -> None:
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
                "W": "3",
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


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    game.deployment_zones = {
        sm_player.id: {"mission_zones": [_RectZone(0.0, 30.0, 0.0, 44.0)]},
        enemy_player.id: {"mission_zones": [_RectZone(30.0, 60.0, 0.0, 44.0)]},
    }
    return game, sm_army, enemy_army, sm_player, enemy_player


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _set_location(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (0.1 * index), float(y), 0.0, 0.0)


def test_terminator_assault_squad_teleport_homer_queues_marker_placement_request():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    terminators = _actual_unit("Terminator Assault Squad", datasheet_id="000000118")
    sm_army.add_unit(terminators)
    _register_units(game, terminators)

    game._apply_teleport_homer_declarations()

    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert request.decision_type == DECISION_PICK_POINT
    assert str((request.context or {}).get("ability", "") or "") == "teleport_homer_marker_placement"
    assert str((request.context or {}).get("unit_id", "") or "") == str(get_entity_id(terminators) or "")
    assert str((request.context or {}).get("ability_name", "") or "") == "Teleport Homer"
    assert str((request.player_id or "") or "") == str(sm_player.id or "")


def test_terminator_assault_squad_terminatus_assault_triggers_battleshock_for_engaged_enemy():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    terminators = _actual_unit("Terminator Assault Squad", datasheet_id="000000118")
    enemy = _mock_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _set_location(terminators, 0.0, 0.0)
    _set_location(enemy, 0.0, 0.0)
    _register_units(game, terminators, enemy)

    specs = terminators.unit_start_fight_phase_engagement_battleshock_specs()
    assert len(specs) == 1
    assert str(specs[0].get("source", "") or "") == "Terminatus Assault"
    assert int(specs[0].get("penalty", 0) or 0) == 0

    enemy.battleshock_turns = []
    enemy.last_battleshock_modifier = None

    def _take_battleshock(turn):
        enemy.battleshock_turns.append(int(turn))
        enemy.last_battleshock_modifier = enemy.special_rules.get("battle_shock_test_modifier")

    enemy.take_battle_shock_test = _take_battleshock

    game._on_phase_start_engagement_battleshock(player=sm_player, phase=game.phase)

    assert enemy.battleshock_turns == [2]
    assert enemy.last_battleshock_modifier in (None, 0)
