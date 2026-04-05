from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
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
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(x + (idx * 0.1), y, 0.0, 0.0)


def _profile(unit: Unit, wargear_name: str):
    for wargear in list(unit.models[0].wargear or []):
        if str(getattr(wargear, "name", "") or "") == wargear_name:
            return wargear.profiles["default"]
    raise AssertionError(f"Profile for {wargear_name!r} not found")


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_gladiator_valiant_ferocious_assault_parser_returns_weapon_specific_closest_rule():
    valiant = _actual_unit("Gladiator Valiant", datasheet_id="000001825")

    rule = valiant.get_closest_eligible_hit_bonus_rule(valiant.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "any"
    assert list(rule.get("weapon_names", []) or []) == ["twin las talon"]
    assert tuple(rule.get("require_keywords", ()) or ()) == ("MONSTER", "VEHICLE")
    assert int(rule.get("hit_bonus", 0) or 0) == 1
    assert str(rule.get("source", "") or "") == "Ferocious Assault"


def test_gladiator_valiant_priority_target_acquisition_parser_returns_weapon_specific_closest_rule():
    valiant = _actual_unit("Gladiator Valiant", datasheet_id="000002788")

    rule = valiant.get_closest_eligible_hit_bonus_rule(valiant.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "any"
    assert list(rule.get("weapon_names", []) or []) == ["twin las talon"]
    assert tuple(rule.get("require_keywords", ()) or ()) == ("MONSTER", "VEHICLE")
    assert int(rule.get("hit_bonus", 0) or 0) == 1
    assert str(rule.get("source", "") or "") == "Priority Target Acquisition"


def test_gladiator_valiant_closest_monster_vehicle_hit_bonus_uses_keyword_filtered_targeting():
    game, sm_army, enemy_army = _build_game()
    valiant = _actual_unit("Gladiator Valiant", datasheet_id="000001825")
    close_infantry = _actual_unit("Intercessor Squad")
    close_vehicle = _actual_unit("Rhino")
    far_monster = _actual_unit("Ballistus Dreadnought")

    sm_army.add_unit(valiant)
    enemy_army.add_unit(close_infantry)
    enemy_army.add_unit(close_vehicle)
    enemy_army.add_unit(far_monster)

    _deploy(valiant, 0.0, 0.0)
    _deploy(close_infantry, 8.0, 0.0)
    _deploy(close_vehicle, 12.0, 0.0)
    _deploy(far_monster, 18.0, 0.0)
    game.map.units = [valiant, close_infantry, close_vehicle, far_monster]
    game.rebuild_entity_registry()

    las_talon = _profile(valiant, "Twin las-talon")
    multi_melta = _profile(valiant, "Multi-melta")

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        hit_result = las_talon.attack(close_vehicle, valiant.models[0], game_map=game.map).hit_results[0]
    assert bool(hit_result.get("hit"))
    assert int(hit_result.get("final_needed", 0) or 0) == 2
    assert any("Ferocious Assault" in str(mod or "") for mod in list(hit_result.get("modifiers", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        hit_result = las_talon.attack(far_monster, valiant.models[0], game_map=game.map).hit_results[0]
    assert not bool(hit_result.get("hit"))
    assert int(hit_result.get("final_needed", 0) or 0) == 3
    assert not any("Ferocious Assault" in str(mod or "") for mod in list(hit_result.get("modifiers", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        hit_result = multi_melta.attack(close_vehicle, valiant.models[0], game_map=game.map).hit_results[0]
    assert not bool(hit_result.get("hit"))
    assert int(hit_result.get("final_needed", 0) or 0) == 3
    assert not any("Ferocious Assault" in str(mod or "") for mod in list(hit_result.get("modifiers", []) or []))
