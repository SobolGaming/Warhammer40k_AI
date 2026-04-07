from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(x + (index * 0.1), y, 0.0, 0.0)


def _profile(unit: Unit, wargear_name: str):
    for wargear in list(unit.models[0].wargear or []):
        if str(getattr(wargear, "name", "") or "") == wargear_name:
            return wargear.profiles["default"]
    raise AssertionError(f"Profile for {wargear_name!r} not found")


def test_sternguard_focus_rerolls_wounds_vs_oath_target() -> None:
    _game, sm_army, enemy_army = _build_game()
    sternguard = _actual_unit("Sternguard Veteran Squad", datasheet_id="000002255")
    oath_target = _actual_unit("Outrider Squad", datasheet_id="000002712")
    other_target = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(sternguard)
    enemy_army.add_unit(oath_target)
    enemy_army.add_unit(other_target)
    sm_army.oath_of_moment.set_target(oath_target)

    wound_mods = sternguard.get_unit_wound_reroll_modifiers("ranged", target=oath_target)
    other_mods = sternguard.get_unit_wound_reroll_modifiers("ranged", target=other_target)

    assert bool(wound_mods.get("reroll_wound_full", False)) is True
    assert any("Sternguard Focus" in reason for reason in list(wound_mods.get("reroll_wound_full_reasons", ()) or ()))
    assert bool(other_mods.get("reroll_wound_full", False)) is False


def test_virtuous_onslaught_rerolls_wound_ones_vs_closest_ranged_target() -> None:
    game, sm_army, enemy_army = _build_game()
    sternguard = _actual_unit("Sternguard Veteran Squad", datasheet_id="000004137")
    close_target = _actual_unit("Scout Squad", datasheet_id="000001160")
    far_target = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sm_army.add_unit(sternguard)
    enemy_army.add_unit(close_target)
    enemy_army.add_unit(far_target)

    _set_unit_position(sternguard, 0.0, 0.0)
    _set_unit_position(close_target, 10.0, 0.0)
    _set_unit_position(far_target, 20.0, 0.0)
    game.map.units = [sternguard, close_target, far_target]

    profile = _profile(sternguard, "Sternguard bolt rifle")
    close_wound = profile._wound_target_with_tracking(
        close_target,
        sternguard.models[0],
        {"distance_to_target": 10.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    far_wound = profile._wound_target_with_tracking(
        far_target,
        sternguard.models[0],
        {"distance_to_target": 20.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert 1 in list(close_wound.get("reroll_values", []) or [])
    assert any("Virtuous Onslaught" in reason for reason in list(close_wound.get("reroll_value_reasons", []) or ()))
    assert 1 not in list(far_wound.get("reroll_values", []) or [])
    assert not any("Virtuous Onslaught" in reason for reason in list(far_wound.get("reroll_value_reasons", []) or ()))


def test_virtuous_onslaught_rerolls_wound_ones_vs_closest_melee_target() -> None:
    game, sm_army, enemy_army = _build_game()
    sternguard = _actual_unit("Sternguard Veteran Squad", datasheet_id="000004137")
    close_target = _actual_unit("Scout Squad", datasheet_id="000001160")
    far_target = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(sternguard)
    enemy_army.add_unit(close_target)
    enemy_army.add_unit(far_target)

    _set_unit_position(sternguard, 0.0, 0.0)
    _set_unit_position(close_target, 2.0, 0.0)
    _set_unit_position(far_target, 2.2, 0.0)
    game.map.units = [sternguard, close_target, far_target]

    profile = _profile(sternguard, "Close combat weapon")
    close_wound = profile._wound_target_with_tracking(
        close_target,
        sternguard.models[0],
        {"distance_to_target": 1.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    far_wound = profile._wound_target_with_tracking(
        far_target,
        sternguard.models[0],
        {"distance_to_target": 1.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert 1 in list(close_wound.get("reroll_values", []) or [])
    assert any("Virtuous Onslaught" in reason for reason in list(close_wound.get("reroll_value_reasons", []) or ()))
    assert 1 not in list(far_wound.get("reroll_values", []) or [])
    assert not any("Virtuous Onslaught" in reason for reason in list(far_wound.get("reroll_value_reasons", []) or ()))
