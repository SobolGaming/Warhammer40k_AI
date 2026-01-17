import pytest
from typing import List

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.wargear import Wargear


class MockDatasheet:
    def __init__(self, name: str, movement=6, model_count=1, base_size="32mm", save="4"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [
            {"description": f"{model_count} Test Models"}
        ]
        self.datasheets_models_cost = [
            {"description": f"{model_count} models", "cost": 100}
        ]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(name: str, x: float, y: float, faction: str = "A", model_count: int = 1, save: str = "4") -> Unit:
    ds = MockDatasheet(name, model_count=model_count, save=save)
    unit = Unit(ds)
    for i, m in enumerate(unit.models):
        m.set_location(x + (i * 1.5), y, 0.0, 0.0)
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_armies(game_map: Map, units_a: List[Unit], units_b: List[Unit]):
    army_a = Army("Army A", "Detachment A")
    army_b = Army("Army B", "Detachment B")
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = units_a + units_b
    return army_a, army_b


def _install_deterministic_rolls(monkeypatch, rolls: List[int]):
    import warhammer40k_ai.utility.dice as dice_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    it = iter(rolls)

    def rigged(_expr: str):
        try:
            return next(it)
        except StopIteration:
            return 6

    monkeypatch.setattr(dice_mod, "get_roll", rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", rigged)


class TestOnDeathAbilities:
    def test_shoot_on_death_triggers_before_removal(self, monkeypatch):
        # Rolls: hit=6, wound=6, save=1 (fail)
        _install_deterministic_rolls(monkeypatch, [6, 6, 1])

        game_map = Map(width=48, height=72)
        dying = create_unit("Dying", 10.0, 10.0, faction="A", model_count=1, save="4")
        target = create_unit("Target", 20.0, 10.0, faction="B", model_count=1, save="4")
        attach_to_armies(game_map, [dying], [target])

        # Give dying model a simple ranged weapon
        gun = Wargear({
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2",
            "S": "10",
            "AP": "0",
            "D": "1",
            "description": "",
        })
        dying.models[0].wargear.append(gun)

        # Add Shoot on Death ability (pattern-based)
        dying.possible_abilities.append("Shoot on Death")
        dying._invalidate_ability_cache()

        # Simulate the model being destroyed
        dying.models[0].wounds = 0
        dying.models[0].die(game_map=game_map)

        # The dying model should be removed
        assert dying.is_alive() is False
        # And it should have fired on death, killing the target
        assert target.is_alive() is False

    def test_fight_on_death_triggers_when_engaged(self, monkeypatch):
        # Rolls: hit=6, wound=6, save=1 (fail)
        _install_deterministic_rolls(monkeypatch, [6, 6, 1])

        game_map = Map(width=48, height=72)
        dying = create_unit("Dying", 10.0, 10.0, faction="A", model_count=1, save="4")
        target = create_unit("Target", 11.0, 10.0, faction="B", model_count=1, save="4")  # within engagement range
        attach_to_armies(game_map, [dying], [target])

        sword = Wargear({
            "name": "Test Sword",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "2",
            "S": "10",
            "AP": "0",
            "D": "1",
            "description": "",
        })
        dying.models[0].wargear.append(sword)

        dying.possible_abilities.append("Fight on Death")
        dying._invalidate_ability_cache()

        dying.models[0].wounds = 0
        dying.models[0].die(game_map=game_map)

        assert dying.is_alive() is False
        assert target.is_alive() is False
