from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 1
    return game, sm_army, enemy_army, sm_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def test_reiver_squad_fearsome_assault_forces_battleshock_at_minus_one() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    reivers = _actual_unit("Reiver Squad", datasheet_id="000002718")
    enemy = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sm_army.add_unit(reivers)
    enemy_army.add_unit(enemy)
    _deploy(reivers, 10.0, 10.0)
    _deploy(enemy, 10.0, 10.0)
    game.map.units = [reivers, enemy]
    game.rebuild_entity_registry()
    game.map.is_within_engagement_range = lambda *_args, **_kwargs: True

    enemy.special_rules = {}
    enemy.last_battleshock_modifier = None
    enemy.is_below_half_strength = lambda: False

    def _take_battleshock(turn: int) -> None:
        enemy.last_battleshock_modifier = int(enemy.special_rules.get("battle_shock_test_modifier", 0) or 0)
        enemy.last_battleshock_turn = int(turn)

    enemy.take_battle_shock_test = _take_battleshock

    game._on_phase_start_engagement_battleshock(player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    assert int(getattr(enemy, "last_battleshock_turn", 0) or 0) == 1
    assert enemy.last_battleshock_modifier == -1


def test_reiver_squad_has_deep_strike_from_reiver_grav_chute() -> None:
    reivers = _actual_unit("Reiver Squad", datasheet_id="000002718")

    assert reivers.has_deep_strike() is True
