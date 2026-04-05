from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_STASIS_BOMB_DESCRIPTION = (
    "Each time this model ends a Normal move, if it moved over one or more enemy units (excluding AIRCRAFT units), "
    "you can select one of those enemy units; that unit suffers D3 mortal wounds. Then roll one D6: on a 1-3, "
    "that enemy unit cannot Advance or Fall Back in its next Movement phase; on a 4-6, that enemy unit must Remain "
    "Stationary in its next Movement phase. This ability can only be used once per turn and once per battle per model."
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
                "M": "12",
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
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.auto_resolve_dice_rolls = False
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


def _get_stasis_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("mortal_wounds_kind", "") or "").strip().lower() == "stasis_bomb":
            return request
    return None


def _target_option_id(request, target: Unit) -> str | None:
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    return None


def _resolve_next_roll(game: Game, player: Player, *, fixed_dice: list[int]) -> None:
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    ]
    if not pending:
        raise AssertionError("No pending dice roll request to resolve.")
    request = pending[0]
    context = dict(getattr(request, "context", {}) or {})
    roll_id = context.get("roll_id")
    if roll_id is None:
        raise AssertionError("Roll request missing roll_id.")
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = list(fixed_dice or [])
    resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)


def test_stasis_bomb_applies_remain_stationary_and_cleans_up():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    source = _make_unit(
        "Harpy",
        keywords=["MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    source.possible_abilities = [
        Ability("Stasis Bomb", "TYR", _STASIS_BOMB_DESCRIPTION, "Datasheet", ""),
    ]
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, target, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[target]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=source, action="move")

    request = _get_stasis_request(game)
    assert request is not None
    option_id = _target_option_id(request, target)
    assert option_id
    resolve_decision_command(game, request, option_id, player_id=tyr_player.id)

    _resolve_next_roll(game, tyr_player, fixed_dice=[2])  # D3 mortal wounds
    _resolve_next_roll(game, tyr_player, fixed_dice=[5])  # Restriction roll -> remain stationary

    sr = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr.get("stasis_bomb_active", False)) is True
    assert str(sr.get("stasis_bomb_mode", "") or "") == "remain_stationary"

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    moved = target.move((18.0, 10.0, 0.0), game.map)
    assert not moved
    assert bool(getattr(getattr(target, "round_state", None), "remained_stationary_this_round", False)) is True

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    sr_after = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr_after.get("stasis_bomb_active", False)) is False
    assert "stasis_bomb_mode" not in sr_after


def test_stasis_bomb_low_roll_blocks_advance_fall_back_and_usage_limits():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    source = _make_unit(
        "Harpy",
        keywords=["MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    source.possible_abilities = [
        Ability("Stasis Bomb", "TYR", _STASIS_BOMB_DESCRIPTION, "Datasheet", ""),
    ]
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, target, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[target]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=source, action="move")
    first_request = _get_stasis_request(game)
    assert first_request is not None
    option_id = _target_option_id(first_request, target)
    assert option_id
    resolve_decision_command(game, first_request, option_id, player_id=tyr_player.id)
    _resolve_next_roll(game, tyr_player, fixed_dice=[1])  # D3 mortal wounds
    _resolve_next_roll(game, tyr_player, fixed_dice=[2])  # Restriction roll -> no advance/fall back

    sr = dict(getattr(target, "special_rules", {}) or {})
    assert str(sr.get("stasis_bomb_mode", "") or "") == "no_advance_fall_back"

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    assert target.advance((18.0, 10.0, 0.0), game.map) is False
    assert target.fall_back((18.0, 10.0, 0.0), [], game.map) is False

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[target]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=source, action="move")
    assert _get_stasis_request(game) is None

    game.turn = 2
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[target]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=source, action="move")
    assert _get_stasis_request(game) is None
