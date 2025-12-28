import pytest

from warhammer40k_ai.classes.map import Map, TerrainFactory
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.army import Army


class MockDatasheet:
    def __init__(self, name: str):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class DummyProfile:
    def __init__(self):
        self.range = type("R", (), {"max": 999.0})()
        self.name = "Indirect Torrent Test"

    def is_indirect_fire(self) -> bool:
        return True

    def is_torrent(self) -> bool:
        return True

    def is_pistol(self) -> bool:
        return False

    def is_blast(self) -> bool:
        return False


def _attach_armies(game_map: Map, a: Unit, b: Unit):
    army_a = Army("Army A", "Detachment A")
    army_b = Army("Army B", "Detachment B")
    army_a.add_unit(a)
    army_b.add_unit(b)
    game_map.units = [a, b]


def test_torrent_cannot_target_non_visible_unit_via_indirect_fire():
    game_map = Map(width=48, height=72)

    shooter = Unit(MockDatasheet("Shooter"))
    target = Unit(MockDatasheet("Target"))
    shooter.deployed = True
    target.deployed = True
    shooter.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    target.models[0].set_location(30.0, 10.0, 0.0, 0.0)

    _attach_armies(game_map, shooter, target)

    # Ruins footprint between shooter and target blocks LOS in this engine.
    ruins = TerrainFactory.create_ruins([(15.0, 8.0), (25.0, 8.0), (25.0, 12.0), (15.0, 12.0)], wall_height=4.0, num_floors=1)
    game_map.add_terrain_feature(ruins)

    profile = DummyProfile()
    assert not shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, target, game_map)


