from __future__ import annotations

from unittest.mock import Mock

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
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
    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(x + (idx * 0.5), y, 0.0, 0.0)


def test_execrator_condemnatory_annihilation_parser_returns_unit_kill_aura_spec():
    execrator = _actual_unit("Execrator", datasheet_id="000004135")

    specs = execrator.model_post_fight_destroyed_aura_battleshock_specs(execrator.models[0])

    assert len(specs) == 1
    spec = dict(specs[0] or {})
    assert str(spec.get("source", "") or "") == "Condemnatory Annihilation"
    assert int(spec.get("range", 0) or 0) == 6
    assert bool(spec.get("requires_unit_destroyed_enemy_unit", False)) is True


def test_execrator_condemnatory_annihilation_triggers_from_attached_bodyguard_kill():
    game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    bodyguard = _actual_unit("Crusader Squad")
    execrator = _actual_unit("Execrator", datasheet_id="000004135")
    destroyed_target = _actual_unit("Intercessor Squad")
    enemy_near = _actual_unit("Scout Squad")
    enemy_far = _actual_unit("Scout Squad")

    bodyguard.attached_leaders.append(execrator)
    execrator.attached_to = bodyguard

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(execrator)
    enemy_army.add_unit(destroyed_target)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)

    _deploy(bodyguard, 10.0, 10.0)
    _deploy(execrator, 10.5, 10.0)
    _deploy(destroyed_target, 16.5, 10.0)
    _deploy(enemy_near, 14.0, 10.0)
    _deploy(enemy_far, 30.0, 30.0)
    game.map.units = [bodyguard, destroyed_target, enemy_near, enemy_far]
    game.rebuild_entity_registry()

    destroyed_target.models = []

    near_test = Mock()
    far_test = Mock()
    enemy_near.take_battle_shock_test = near_test
    enemy_far.take_battle_shock_test = far_test

    bodyguard_model = bodyguard.models[0]
    game._on_fight_attacks_resolved_post_fight_battleshock(
        unit=bodyguard,
        attacker_unit=bodyguard,
        hits_by_target={destroyed_target: 1},
        hit_models_by_target={destroyed_target: {bodyguard_model}},
        killing_models_by_target={destroyed_target: {bodyguard_model}},
    )

    near_test.assert_called_once_with(1)
    far_test.assert_not_called()


def test_execrator_condemnatory_annihilation_does_not_trigger_without_destroyed_enemy_unit():
    game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    bodyguard = _actual_unit("Crusader Squad")
    execrator = _actual_unit("Execrator", datasheet_id="000004135")
    enemy_target = _actual_unit("Intercessor Squad")
    enemy_near = _actual_unit("Scout Squad")

    bodyguard.attached_leaders.append(execrator)
    execrator.attached_to = bodyguard

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(execrator)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(enemy_near)

    _deploy(bodyguard, 10.0, 10.0)
    _deploy(execrator, 10.5, 10.0)
    _deploy(enemy_target, 16.5, 10.0)
    _deploy(enemy_near, 14.0, 10.0)
    game.map.units = [bodyguard, enemy_target, enemy_near]
    game.rebuild_entity_registry()

    near_test = Mock()
    enemy_near.take_battle_shock_test = near_test

    bodyguard_model = bodyguard.models[0]
    game._on_fight_attacks_resolved_post_fight_battleshock(
        unit=bodyguard,
        attacker_unit=bodyguard,
        hits_by_target={enemy_target: 1},
        hit_models_by_target={enemy_target: {bodyguard_model}},
        killing_models_by_target={enemy_target: {bodyguard_model}},
    )

    near_test.assert_not_called()
