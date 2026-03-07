from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _make_game() -> tuple[Game, Player, Player]:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    tau_army = Army("T'au Empire", "Kauyon")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
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


def _first_profile(unit: Unit, *, ranged: bool):
    model = unit.models[0]
    for wargear in list(getattr(model, "wargear", []) or []):
        if ranged and not wargear.is_ranged():
            continue
        if (not ranged) and not wargear.is_melee():
            continue
        return next(iter(wargear.profiles.values()))
    kind = "ranged" if ranged else "melee"
    raise AssertionError(f"Expected a {kind} weapon profile on {unit.name}.")


def test_hero_of_the_empire_grants_ranged_hit_reroll_ones_within_six_inches():
    game, tau_player, enemy_player = _make_game()
    shadowsun = _make_tau_unit("Commander Shadowsun")
    attacker = _make_tau_unit("Strike Team")
    target = _make_tau_unit("Breacher Team")

    tau_player.army.add_unit(shadowsun)
    tau_player.army.add_unit(attacker)
    enemy_player.army.add_unit(target)

    _deploy_unit(shadowsun, 0.0, 0.0)
    _deploy_unit(attacker, 5.0, 0.0)
    _deploy_unit(target, 20.0, 0.0)
    game.map.units = [shadowsun, attacker, target]

    profile = _first_profile(attacker, ranged=True)
    mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game.map)

    assert bool(mods.reroll_hit_ones)
    assert any("re-roll Hit rolls of 1" in str(reason) for reason in list(mods.reroll_hit_reasons or ()))


def test_hero_of_the_empire_does_not_apply_to_melee_attacks():
    game, tau_player, enemy_player = _make_game()
    shadowsun = _make_tau_unit("Commander Shadowsun")
    attacker = _make_tau_unit("Strike Team")
    target = _make_tau_unit("Breacher Team")

    tau_player.army.add_unit(shadowsun)
    tau_player.army.add_unit(attacker)
    enemy_player.army.add_unit(target)

    _deploy_unit(shadowsun, 0.0, 0.0)
    _deploy_unit(attacker, 5.0, 0.0)
    _deploy_unit(target, 20.0, 0.0)
    game.map.units = [shadowsun, attacker, target]

    profile = _first_profile(attacker, ranged=False)
    mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game.map)

    assert not bool(mods.reroll_hit_ones)


def test_hero_of_the_empire_does_not_apply_outside_six_inches():
    game, tau_player, enemy_player = _make_game()
    shadowsun = _make_tau_unit("Commander Shadowsun")
    attacker = _make_tau_unit("Strike Team")
    target = _make_tau_unit("Breacher Team")

    tau_player.army.add_unit(shadowsun)
    tau_player.army.add_unit(attacker)
    enemy_player.army.add_unit(target)

    _deploy_unit(shadowsun, 0.0, 0.0)
    _deploy_unit(attacker, 7.5, 0.0)
    _deploy_unit(target, 20.0, 0.0)
    game.map.units = [shadowsun, attacker, target]

    profile = _first_profile(attacker, ranged=True)
    mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game.map)

    assert not bool(mods.reroll_hit_ones)
