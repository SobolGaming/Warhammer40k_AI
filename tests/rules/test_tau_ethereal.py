from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _make_game() -> tuple[Game, Player, Player]:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    tau_army = Army.with_detachment("T'au Empire", "Kauyon")
    tau_army.faction_id = "TAU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tau_player = Player("TAU", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    return game, tau_player, enemy_player


def _make_tau_unit(name: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, faction_id="TAU")
    assert datasheet is not None
    return Unit(datasheet)


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


def test_ethereal_hover_drone_grants_fly_and_sets_move_when_equipped():
    ethereal = _make_tau_unit("Ethereal")
    model = ethereal.models[0]
    model.optional_wargear.append("Hover Drone")

    ethereal._refresh_bearer_keyword_flags()

    move = ethereal.get_effective_model_characteristic(model, "movement")

    assert ethereal.has_keyword("FLY") is True
    assert int(move) == 10


def test_ethereal_coordinated_leadership_end_command_phase_roll_gains_cp():
    game, tau_player, enemy_player = _make_game()
    ethereal = _make_tau_unit("Ethereal")
    enemy = _make_tau_unit("Breacher Team")

    tau_player.army.add_unit(ethereal)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(ethereal, 0.0, 0.0)
    _deploy_unit(enemy, 20.0, 0.0)
    game.map.units = [ethereal, enemy]
    game.rebuild_entity_registry()

    specs = list(ethereal.special_rules.get("command_phase_end_bonus_cp_roll_specs", []) or [])
    assert len(specs) == 1
    assert str(specs[0].get("source", "")) == "Coordinated Leadership"
    assert int(specs[0].get("dice_count", 0) or 0) == 1
    assert int(specs[0].get("threshold", 0) or 0) == 4
    assert int(specs[0].get("cp", 0) or 0) == 1

    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    before_cp = int(tau_player.command_points or 0)
    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", return_value=4):
        game._on_phase_end_leadership_cp_gain(player=tau_player, phase=game.phase)
    after_cp = int(tau_player.command_points or 0)

    assert after_cp == before_cp + 1

