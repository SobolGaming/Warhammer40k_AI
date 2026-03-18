from __future__ import annotations

from types import SimpleNamespace

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


def test_gladiator_reaper_rotating_death_parser_returns_weapon_keyword_rule():
    reaper = _actual_unit("Gladiator Reaper", datasheet_id="000001667")

    rule = reaper.get_weapon_target_keywords_keyword_bonus_rule(reaper.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "ranged"
    assert list(rule.get("weapon_names", []) or []) == ["twin heavy onslaught gatling cannon"]
    assert str(rule.get("keyword", "") or "") == "SUSTAINED HITS 2"
    assert tuple(rule.get("target_keywords_any", ()) or ()) == ("INFANTRY",)
    assert str(rule.get("source", "") or "") == "Rotating Death"


def test_gladiator_reaper_reaping_tally_parser_returns_weapon_keyword_rule():
    reaper = _actual_unit("Gladiator Reaper", datasheet_id="000002789")

    rule = reaper.get_weapon_target_keywords_keyword_bonus_rule(reaper.models[0])

    assert isinstance(rule, dict)
    assert str(rule.get("attack_type", "") or "") == "ranged"
    assert list(rule.get("weapon_names", []) or []) == ["twin heavy onslaught gatling cannon"]
    assert str(rule.get("keyword", "") or "") == "SUSTAINED HITS 2"
    assert tuple(rule.get("target_keywords_any", ()) or ()) == ("INFANTRY",)
    assert str(rule.get("source", "") or "") == "Reaping Tally"


def test_gladiator_reaper_rotating_death_grants_sustained_hits_only_vs_infantry():
    game, sm_army, enemy_army = _build_game()
    reaper = _actual_unit("Gladiator Reaper", datasheet_id="000001667")
    infantry_target = _actual_unit("Intercessor Squad")
    vehicle_target = _actual_unit("Rhino")

    sm_army.add_unit(reaper)
    enemy_army.add_unit(infantry_target)
    enemy_army.add_unit(vehicle_target)

    _deploy(reaper, 0.0, 0.0)
    _deploy(infantry_target, 18.0, 0.0)
    _deploy(vehicle_target, 20.0, 0.0)
    game.map.units = [reaper, infantry_target, vehicle_target]
    game.rebuild_entity_registry()

    profile = _profile(reaper, "Twin heavy onslaught gatling cannon")

    infantry_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        infantry_target,
        reaper.models[0],
        infantry_attack,
        roll_value=6,
        allow_rerolls=False,
    )
    assert int(infantry_attack.get("sustained_hit", 0) or 0) == 2

    vehicle_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        vehicle_target,
        reaper.models[0],
        vehicle_attack,
        roll_value=6,
        allow_rerolls=False,
    )
    assert int(vehicle_attack.get("sustained_hit", 0) or 0) == 0
