from warhammer40k_ai.classes.map import Map, TerrainFactory
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.classes.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


class _StubGame:
    def __init__(self, game_map):
        self.map = game_map


class _StubPlayer:
    def __init__(self, game):
        self.game = game


class _StubArmy:
    def __init__(self, player):
        self.player = player


class _StubUnit:
    def __init__(self, name, models, army):
        self.name = name
        self.models = models
        self._army = army
        for m in self.models:
            m.set_parent_unit(self)

    def get_parent_army(self):
        return self._army


def _make_model(name: str, x: float, y: float, z: float) -> Model:
    b = Base(BaseType.CIRCULAR, 0.5)
    m = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=6,
        objective_control=1,
        model_base=b,
    )
    m.set_location(x, y, z, 0.0)
    return m


def test_plunging_fire_improves_ap_by_1_when_conditions_met():
    game_map = Map(width=60, height=44)
    # Simple 10x10 RUINS footprint with at least 2 upper floors (z=6"+)
    ruins = TerrainFactory.create_ruins([(0, 0), (10, 0), (10, 10), (0, 10)], num_floors=2)
    game_map.add_terrain_feature(ruins)

    game = _StubGame(game_map)
    player = _StubPlayer(game)
    army = _StubArmy(player)

    attacker = _make_model("attacker", x=5, y=5, z=6.12)  # 2nd floor surface
    target_model = _make_model("target", x=20, y=20, z=0.0)

    attacker_unit = _StubUnit("attacker_unit", [attacker], army)
    target_unit = _StubUnit("target_unit", [target_model], army)  # army doesn't matter for AP calc

    wargear = Wargear(
        {
            "name": "Test Gun",
            "type": "ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )
    profile = wargear.profiles["default"]

    assert profile.get_effective_ap(attacker, target_unit) == -2


def test_plunging_fire_requires_attacker_z_at_least_6():
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins([(0, 0), (10, 0), (10, 10), (0, 10)], num_floors=2)
    game_map.add_terrain_feature(ruins)

    game = _StubGame(game_map)
    player = _StubPlayer(game)
    army = _StubArmy(player)

    attacker = _make_model("attacker", x=5, y=5, z=3.12)  # 1st floor surface (<6")
    target_model = _make_model("target", x=20, y=20, z=0.0)
    attacker_unit = _StubUnit("attacker_unit", [attacker], army)
    target_unit = _StubUnit("target_unit", [target_model], army)

    wargear = Wargear(
        {
            "name": "Test Gun",
            "type": "ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )
    profile = wargear.profiles["default"]

    assert profile.get_effective_ap(attacker, target_unit) == -1


def test_plunging_fire_requires_target_unit_all_ground_level():
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins([(0, 0), (10, 0), (10, 10), (0, 10)], num_floors=2)
    game_map.add_terrain_feature(ruins)

    game = _StubGame(game_map)
    player = _StubPlayer(game)
    army = _StubArmy(player)

    attacker = _make_model("attacker", x=5, y=5, z=6.12)
    # One target model elevated => should disable Plunging Fire
    target1 = _make_model("target1", x=20, y=20, z=0.0)
    target2 = _make_model("target2", x=21, y=20, z=2.0)
    attacker_unit = _StubUnit("attacker_unit", [attacker], army)
    target_unit = _StubUnit("target_unit", [target1, target2], army)

    wargear = Wargear(
        {
            "name": "Test Gun",
            "type": "ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = wargear.profiles["default"]

    assert profile.get_effective_ap(attacker, target_unit) == 0


def test_plunging_fire_requires_attacker_wholly_within_ruins():
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins([(0, 0), (10, 0), (10, 10), (0, 10)], num_floors=2)
    game_map.add_terrain_feature(ruins)

    game = _StubGame(game_map)
    player = _StubPlayer(game)
    army = _StubArmy(player)

    # Put the attacker outside ruins footprint but at high z anyway
    attacker = _make_model("attacker", x=20, y=20, z=6.12)
    target_model = _make_model("target", x=30, y=30, z=0.0)
    attacker_unit = _StubUnit("attacker_unit", [attacker], army)
    target_unit = _StubUnit("target_unit", [target_model], army)

    wargear = Wargear(
        {
            "name": "Test Gun",
            "type": "ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = wargear.profiles["default"]

    assert profile.get_effective_ap(attacker, target_unit) == 0

