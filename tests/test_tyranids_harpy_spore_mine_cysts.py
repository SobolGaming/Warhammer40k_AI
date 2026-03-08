from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_PICK_POINT,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_SPORE_MINE_CYSTS_DESCRIPTION = (
    "Each time this model ends a Normal move, you can select one of the following: "
    "- Select one enemy unit it moved over during that move and roll six D6: for each 3+, that unit suffers 1 mortal wound. "
    "- Add one new Spore Mines unit containing D3 models to your army and set it up anywhere on the battlefield that is wholly "
    "within 6\" of this model and more than 9\" horizontally away from all enemy units. "
    "You cannot select this option for more than one model per turn."
)


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "14",
                "T": "8",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _get_spore_mine_cysts_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() == "spore_mine_cysts":
            return request
    return None


def _get_spawn_pick_point_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_PICK_POINT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() == "parasitic_infection_spawn":
            return request
    return None


def _target_option_id(request, target: Unit) -> str | None:
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    return None


def _spawn_option_id(request) -> str | None:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "spawn_spore_mines":
            return str(getattr(option, "option_id", "") or "")
    return None


def _confirm_option_id(request) -> str | None:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "confirm":
            return str(getattr(option, "option_id", "") or "")
    return None


def test_spore_mine_cysts_queues_target_or_spawn_choice():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    harpy = _make_unit("Harpy", keywords=["MONSTER", "FLY"], faction_keywords=["TYRANIDS"])
    harpy.possible_abilities = [Ability("Spore Mine Cysts", "TYR", _SPORE_MINE_CYSTS_DESCRIPTION, "Datasheet", "")]
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(harpy)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, harpy, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[enemy]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=harpy, action="move")

    request = _get_spore_mine_cysts_request(game)
    assert request is not None
    assert _target_option_id(request, enemy) is not None
    assert _spawn_option_id(request) is not None


def test_spore_mine_cysts_target_option_requests_six_d6_mortal_roll():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    harpy = _make_unit("Harpy", keywords=["MONSTER", "FLY"], faction_keywords=["TYRANIDS"])
    harpy.possible_abilities = [Ability("Spore Mine Cysts", "TYR", _SPORE_MINE_CYSTS_DESCRIPTION, "Datasheet", "")]
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(harpy)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, harpy, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[enemy]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=harpy, action="move")

    request = _get_spore_mine_cysts_request(game)
    assert request is not None
    option_id = _target_option_id(request, enemy)
    assert option_id is not None
    resolved = resolve_decision_command(game, request, option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False))

    roll_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_REQUEST_DICE_ROLL]
    assert roll_requests
    roll_request = roll_requests[0]
    roll_id = int((roll_request.context or {}).get("roll_id", 0) or 0)
    assert roll_id > 0
    state = game.roll_manager.get_roll(roll_id)
    spec = dict(getattr(state, "spec", {}) or {})
    assert int(spec.get("dice_count", 0) or 0) == 6
    assert int(spec.get("target", 0) or 0) == 3
    assert str(spec.get("roll_type", "") or "").strip().lower() == "move_over_mortal_wounds"


def test_spore_mine_cysts_spawn_option_queues_pick_point_and_spawns():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    harpy = _make_unit("Harpy", keywords=["MONSTER", "FLY"], faction_keywords=["TYRANIDS"])
    harpy.possible_abilities = [Ability("Spore Mine Cysts", "TYR", _SPORE_MINE_CYSTS_DESCRIPTION, "Datasheet", "")]
    tyr_army.add_unit(harpy)
    _deploy_unit(game, harpy, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=harpy, action="move")

    request = _get_spore_mine_cysts_request(game)
    assert request is not None
    spawn_option = _spawn_option_id(request)
    assert spawn_option is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        resolved = resolve_decision_command(game, request, spawn_option, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False))

    pick_req = _get_spawn_pick_point_request(game)
    assert pick_req is not None
    ctx = dict(getattr(pick_req, "context", {}) or {})
    assert str(ctx.get("spawn_unit_name", "") or "").strip().lower() == "spore mines"
    assert int(ctx.get("spawn_model_count", 0) or 0) == 2
    assert int(ctx.get("setup_range", 0) or 0) == 6

    confirm_id = _confirm_option_id(pick_req)
    assert confirm_id is not None
    confirm_resolved = resolve_decision_command(
        game,
        pick_req,
        confirm_id,
        result_payload={"point": [13.0, 10.0]},
        player_id=tyr_player.id,
    )
    assert bool(getattr(confirm_resolved, "ok", False))

    spawned_units = [
        unit
        for unit in list(getattr(tyr_army, "units", []) or [])
        if str(getattr(unit, "name", "") or "").strip().lower() == "spore mines"
        and bool(getattr(unit, "spawned_in_battle", False))
    ]
    assert len(spawned_units) == 1
    assert len(list(getattr(spawned_units[0], "models", []) or [])) == 2

    sr = dict(getattr(harpy, "special_rules", {}) or {})
    assert bool(sr.get("spore_mine_cysts_spawn_used_this_turn")) is True
    assert int(sr.get("spore_mine_cysts_spawn_turn", 0) or 0) == int(getattr(game, "turn", 0) or 0)
