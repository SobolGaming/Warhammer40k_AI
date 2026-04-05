from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, necron_units: list[Unit], enemy_units: list[Unit]):
    necron_army = Army("Necrons", "Annihilation Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(necron_units or []):
        necron_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    necron_player = Player("Necron Player", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.map.units = list(necron_units or []) + list(enemy_units or [])
    return game


def _set_xy(unit: Unit, x: float, y: float) -> None:
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _make_ranged_profile(*, ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(
        name="Gauss Blaster",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": str(int(ap)),
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def test_annihilation_protocol_charge_reroll_applies_for_eligible_units():
    destroyer = _create_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
    )
    flayed = _create_unit(
        "Flayed Ones",
        keywords=["INFANTRY", "FLAYED ONES"],
        faction_keywords=["NECRONS"],
    )
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game = _build_game(necron_units=[destroyer, flayed, warriors], enemy_units=[enemy])

    assert bool(destroyer.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))
    assert bool(flayed.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))
    assert not bool(warriors.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))


def test_annihilation_protocol_charge_bonus_applies_vs_below_half_strength_target():
    destroyer = _create_unit(
        "Lokhust Destroyers",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy_below_half = _create_unit("Enemy Damaged", keywords=["INFANTRY"])
    enemy_full = _create_unit("Enemy Full", keywords=["INFANTRY"])
    game = _build_game(necron_units=[destroyer], enemy_units=[enemy_below_half, enemy_full])

    enemy_below_half.is_below_half_strength = lambda: True
    enemy_full.is_below_half_strength = lambda: False

    below_half_mods = game.get_charge_roll_modifiers(destroyer, target_unit=enemy_below_half)
    assert any(int(value) == 1 and "Annihilation Protocol" in str(source) for value, source in below_half_mods)

    full_strength_mods = game.get_charge_roll_modifiers(destroyer, target_unit=enemy_full)
    assert not any("Annihilation Protocol" in str(source) for _value, source in full_strength_mods)


def test_annihilation_protocol_ranged_ap_bonus_requires_destroyer_and_closest_target():
    destroyer = _create_unit(
        "Hexmark Destroyer",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
    )
    flayed = _create_unit(
        "Flayed Ones",
        keywords=["INFANTRY", "FLAYED ONES"],
        faction_keywords=["NECRONS"],
    )
    close_enemy = _create_unit("Close Enemy", keywords=["INFANTRY"])
    far_enemy = _create_unit("Far Enemy", keywords=["INFANTRY"])

    game = _build_game(necron_units=[destroyer, flayed], enemy_units=[close_enemy, far_enemy])
    _set_xy(destroyer, 0.0, 0.0)
    _set_xy(flayed, 0.0, 2.0)
    _set_xy(close_enemy, 8.0, 0.0)
    _set_xy(far_enemy, 16.0, 0.0)
    game.map.units = [destroyer, flayed, close_enemy, far_enemy]

    profile = _make_ranged_profile(ap=0)
    assert int(profile.get_effective_ap(destroyer.models[0], close_enemy)) == -1
    assert int(profile.get_effective_ap(destroyer.models[0], far_enemy)) == 0
    assert int(profile.get_effective_ap(flayed.models[0], close_enemy)) == 0
