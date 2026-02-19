from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.deployment_zones = {
        p1.id: {"mission_zones": [_RectZone(0.0, 20.0, 0.0, 20.0)]},
        p2.id: {"mission_zones": [_RectZone(80.0, 100.0, 0.0, 20.0)]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)
    return game, admech_army, enemy_army, p1, p2


def _find_rad_bombardment_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "rad_bombardment"
    ]


def test_rad_bombardment_round_one_queues_opponent_choices():
    game, admech_army, enemy_army, _p1, enemy_player = _build_game()
    inside = _make_unit("Enemy Vanguard", keywords=["INFANTRY"])
    outside = _make_unit("Enemy Rearguard", keywords=["INFANTRY"])
    enemy_army.add_unit(inside)
    enemy_army.add_unit(outside)
    inside.models[0].set_location(90.0, 10.0, 0.0, 0.0)
    outside.models[0].set_location(60.0, 10.0, 0.0, 0.0)
    game.map.units = [inside, outside]
    game.rebuild_entity_registry()

    admech_army.on_battle_round_start(1)
    requests = _find_rad_bombardment_requests(game)
    assert len(requests) == 1

    request = requests[0]
    assert request.player_id == enemy_player.id
    choices = {
        str((opt.payload or {}).get("rad_bombardment_choice", "") or "")
        for opt in list(request.options or [])
    }
    assert choices == {"stand_firm", "take_cover"}
    assert str((request.context or {}).get("target_unit_id", "") or "") == str(get_entity_id(inside) or "")


def test_rad_bombardment_stand_firm_applies_mortal_wounds_on_three_plus():
    game, admech_army, enemy_army, _p1, enemy_player = _build_game()
    target = _make_unit("Enemy Vanguard", keywords=["INFANTRY"])
    enemy_army.add_unit(target)
    target.models[0].set_location(90.0, 10.0, 0.0, 0.0)
    game.map.units = [target]
    game.rebuild_entity_registry()

    admech_army.on_battle_round_start(1)
    request = _find_rad_bombardment_requests(game)[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("rad_bombardment_choice", "") or "") == "stand_firm"
    )

    target._apply_mortal_wounds_to_unit = Mock()
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[3, 2]):
        result = resolve_decision_command(game, request, option.option_id, player_id=enemy_player.id)

    assert bool(getattr(result, "ok", False)) is True
    target._apply_mortal_wounds_to_unit.assert_called_once()
    assert target._apply_mortal_wounds_to_unit.call_args.args[0] is target
    assert int(target._apply_mortal_wounds_to_unit.call_args.args[1] or 0) == 2
    assert bool(target.is_battle_shocked()) is False


def test_rad_bombardment_take_cover_battleshock_persists_until_next_round_start():
    game, admech_army, enemy_army, _p1, enemy_player = _build_game()
    target = _make_unit("Enemy Vanguard", keywords=["INFANTRY"])
    enemy_army.add_unit(target)
    target.models[0].set_location(90.0, 10.0, 0.0, 0.0)
    game.map.units = [target]
    game.rebuild_entity_registry()

    admech_army.on_battle_round_start(1)
    request = _find_rad_bombardment_requests(game)[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("rad_bombardment_choice", "") or "") == "take_cover"
    )

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        result = resolve_decision_command(game, request, option.option_id, player_id=enemy_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bool(target.is_battle_shocked()) is True

    game.current_player_index = 1
    game.start_command_phase()
    assert bool(target.is_battle_shocked()) is True

    game.turn = 2
    admech_army.on_battle_round_start(2)
    assert bool(target.is_battle_shocked()) is False


def test_rad_bombardment_invalid_choice_is_rejected():
    game, admech_army, enemy_army, _p1, enemy_player = _build_game()
    target = _make_unit("Enemy Vanguard", keywords=["INFANTRY"])
    enemy_army.add_unit(target)
    target.models[0].set_location(90.0, 10.0, 0.0, 0.0)
    game.map.units = [target]
    game.rebuild_entity_registry()

    admech_army.on_battle_round_start(1)
    request = _find_rad_bombardment_requests(game)[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("rad_bombardment_choice", "") or "") == "stand_firm"
    )
    option.payload["rad_bombardment_choice"] = "invalid_choice"

    result = resolve_decision_command(game, request, option.option_id, player_id=enemy_player.id)
    assert bool(getattr(result, "ok", False)) is False


def test_rad_bombardment_fallout_applies_in_rounds_two_to_five():
    game, admech_army, enemy_army, _p1, _p2 = _build_game()
    inside = _make_unit("Enemy Vanguard", keywords=["INFANTRY"])
    outside = _make_unit("Enemy Rearguard", keywords=["INFANTRY"])
    enemy_army.add_unit(inside)
    enemy_army.add_unit(outside)
    inside.models[0].set_location(90.0, 10.0, 0.0, 0.0)
    outside.models[0].set_location(60.0, 10.0, 0.0, 0.0)
    game.map.units = [inside, outside]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0

    inside._apply_mortal_wounds_to_unit = Mock()
    inside.take_battle_shock_test = Mock()
    outside._apply_mortal_wounds_to_unit = Mock()
    outside.take_battle_shock_test = Mock()

    with patch("warhammer40k_ai.rules.adeptus_mechanicus_detachments.get_roll", return_value=3):
        game.start_command_phase()

    inside._apply_mortal_wounds_to_unit.assert_called_once()
    assert inside._apply_mortal_wounds_to_unit.call_args.args[0] is inside
    assert int(inside._apply_mortal_wounds_to_unit.call_args.args[1] or 0) == 1
    inside.take_battle_shock_test.assert_called_once_with(2)
    outside._apply_mortal_wounds_to_unit.assert_not_called()
    outside.take_battle_shock_test.assert_not_called()
