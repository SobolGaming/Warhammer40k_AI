from __future__ import annotations

from unittest.mock import Mock

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str | None = None, faction_id: str = "SM") -> Unit:
    kwargs = {"faction_id": faction_id}
    if datasheet_id:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(x + (idx * 0.5), y, 0.0, 0.0)


def test_ezekiel_engulfing_fear_parser_returns_shooting_phase_battleshock_spec():
    ezekiel = _actual_unit("Ezekiel", datasheet_id="000000226")

    specs = ezekiel.model_start_selected_phases_enemy_range_battleshock_specs(ezekiel.models[0])
    engulfing_fear = next(spec for spec in list(specs or []) if str(spec.get("source", "") or "") == "Engulfing Fear (Psychic)")

    assert int(engulfing_fear.get("range", 0) or 0) == 18
    assert int(engulfing_fear.get("test_penalty", 0) or 0) == 0
    assert list(engulfing_fear.get("phase_names", []) or []) == ["SHOOTING_PHASE"]
    assert bool(engulfing_fear.get("optional", False)) is True
    assert str(engulfing_fear.get("context_ability", "") or "") == "phase_select_enemy_battleshock"


def test_ezekiel_engulfing_fear_queues_and_applies_battleshock_in_shooting_phase():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    ezekiel = _actual_unit("Ezekiel", datasheet_id="000000226")
    target = _actual_unit("Intercessor Squad")
    far_target = _actual_unit("Scout Squad")

    sm_army.add_unit(ezekiel)
    enemy_army.add_unit(target)
    enemy_army.add_unit(far_target)

    _deploy(ezekiel, 10.0, 10.0)
    _deploy(target, 24.0, 10.0)
    _deploy(far_target, 40.0, 40.0)
    game.map.units = [ezekiel, target, far_target]
    game.rebuild_entity_registry()

    target.force_battle_shock_test = Mock()
    far_target.force_battle_shock_test = Mock()

    game.event_system.publish("phase_start", player=sm_player, phase=game.phase)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "phase_select_enemy_battleshock"
    )
    target_option = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(target._id)
    )
    outcome = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)

    assert bool(getattr(outcome, "ok", False))
    target.force_battle_shock_test.assert_called_once_with(2, modifier=0, source="Engulfing Fear (Psychic)")
    far_target.force_battle_shock_test.assert_not_called()


def test_ezekiel_book_of_salvation_adds_one_melee_attack_while_leading():
    army = Army.with_detachment("Space Marines", detachment_type="Other")
    army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    ezekiel = _actual_unit("Ezekiel", datasheet_id="000000226")
    bodyguard = _actual_unit("Intercessor Squad")
    target = _actual_unit("Intercessor Squad")

    army.add_unit(bodyguard)
    army.add_unit(ezekiel)
    enemy_army.add_unit(target)

    bodyguard.attached_leaders.append(ezekiel)
    ezekiel.attached_to = bodyguard

    attacker_model = bodyguard.models[0]
    profile = Wargear(
        {
            "name": "Close combat weapon",
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]

    info = profile.preview_attack_count(target, attacker_model)

    assert int(info.num_attacks) == 3


def test_ezekiel_book_of_salvation_triggers_friendly_battleshock_within_range_when_destroyed():
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    game.turn = 3

    ezekiel = _actual_unit("Ezekiel", datasheet_id="000000226")
    bodyguard = _actual_unit("Intercessor Squad")
    nearby = _actual_unit("Scout Squad")
    far = _actual_unit("Scout Squad")

    bodyguard.attached_leaders.append(ezekiel)
    ezekiel.attached_to = bodyguard

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(ezekiel)
    sm_army.add_unit(nearby)
    sm_army.add_unit(far)

    _deploy(bodyguard, 10.0, 10.0)
    _deploy(ezekiel, 10.5, 10.0)
    _deploy(nearby, 14.0, 10.0)
    _deploy(far, 30.0, 30.0)
    game.map.units = [bodyguard, nearby, far]
    game.rebuild_entity_registry()

    bodyguard.force_battle_shock_test = Mock()
    nearby.force_battle_shock_test = Mock()
    far.force_battle_shock_test = Mock()

    game.event_system.publish(
        "model_destroyed",
        target_model=ezekiel.models[0],
        target_unit=ezekiel,
        game_map=game.map,
    )

    bodyguard.force_battle_shock_test.assert_called_once_with(3, modifier=0, source="Book of Salvation")
    nearby.force_battle_shock_test.assert_called_once_with(3, modifier=0, source="Book of Salvation")
    far.force_battle_shock_test.assert_not_called()
