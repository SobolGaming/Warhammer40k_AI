from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
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


def _make_tau_unit(name: str, datasheet_id: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="TAU")
    assert datasheet is not None
    return Unit(datasheet)


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


def _shasui_model(unit: Unit):
    for model in list(getattr(unit, "models", []) or []):
        if "shas'ui" in str(getattr(model, "name", "")).lower():
            return model
    raise AssertionError("Expected a Shas'ui model in unit composition.")


def _support_turret_count(model) -> int:
    total = 0
    for wargear in list(getattr(model, "wargear", []) or []):
        if "support turret" in str(getattr(wargear, "name", "") or "").lower():
            total += 1
    return total


def test_ds8_support_turret_applies_then_clears_across_movement_phases():
    game, tau_player, _enemy_player = _make_game()
    breachers = _make_tau_unit("Breacher Team", "000000412")
    tau_player.army.add_unit(breachers)
    _deploy_unit(breachers, 10.0, 10.0)
    game.map.units = [breachers]

    shasui = _shasui_model(breachers)
    assert _support_turret_count(shasui) == 0

    breachers.round_state.remained_stationary_this_round = True
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_end_ds8_support_turret(player=tau_player, phase=game.phase)

    assert _support_turret_count(shasui) == 1
    assert bool(breachers.special_rules.get("ds8_support_turret_active", False))

    game._on_phase_start_ds8_support_turret_cleanup(player=tau_player, phase=game.phase)

    assert _support_turret_count(shasui) == 0
    assert "ds8_support_turret_active" not in breachers.special_rules


def test_ds8_support_turret_not_applied_when_unit_did_not_remain_stationary():
    game, tau_player, _enemy_player = _make_game()
    strike_team = _make_tau_unit("Strike Team", "000000411")
    tau_player.army.add_unit(strike_team)
    _deploy_unit(strike_team, 12.0, 8.0)
    game.map.units = [strike_team]

    shasui = _shasui_model(strike_team)
    assert _support_turret_count(shasui) == 0

    strike_team.round_state.remained_stationary_this_round = False
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_end_ds8_support_turret(player=tau_player, phase=game.phase)

    assert _support_turret_count(shasui) == 0
    assert not bool(strike_team.special_rules.get("ds8_support_turret_active", False))
