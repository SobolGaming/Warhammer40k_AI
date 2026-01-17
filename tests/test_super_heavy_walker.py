import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _ModelStub:
    def __init__(self, base):
        self.model_base = base
        self.is_alive = True
        self.parent_unit = None

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z)


class _UnitStub:
    def __init__(self, *, titanic=False):
        self.is_titanic = titanic
        self.deployed = True
        self.models = []

    def is_alive(self):
        return True


class _MapStub:
    def __init__(self, units):
        self.units = list(units or [])

    def is_within_boundary(self, *_args, **_kwargs):
        return True


class TestSuperHeavyWalker(unittest.TestCase):
    def test_validation_rules_include_super_heavy_walker_overrides(self):
        from warhammer40k_ai.utility.calcs import get_validation_rules, MovementType

        class _Mover:
            def has_super_heavy_walker(self):
                return True

        rules = get_validation_rules(MovementType.MOVE, moving_unit=_Mover())
        self.assertTrue(rules.get("can_move_through_models"))
        self.assertTrue(rules.get("block_titanic_models"))
        self.assertTrue(rules.get("cannot_end_in_engagement_range"))
        self.assertFalse(rules.get("cannot_move_within_engagement_range"))

        rules_fb = get_validation_rules(MovementType.FALL_BACK, moving_unit=_Mover())
        self.assertTrue(rules_fb.get("can_move_through_models"))
        self.assertTrue(rules_fb.get("block_titanic_models"))
        self.assertTrue(rules_fb.get("cannot_end_in_engagement_range"))

    def test_titanic_models_block_super_heavy_walker(self):
        from warhammer40k_ai.utility.calcs import is_position_valid_unified_detailed
        from warhammer40k_ai.utility.model_base import Base, BaseType

        moving_base = Base(BaseType.CIRCULAR, 1.0)
        moving_base.set_position(0.0, 0.0, 0.0)
        moving_model = _ModelStub(moving_base)
        moving_unit = _UnitStub(titanic=False)
        moving_model.parent_unit = moving_unit

        titanic_base = Base(BaseType.CIRCULAR, 1.0)
        titanic_base.set_position(2.0, 2.0, 0.0)
        titanic_model = _ModelStub(titanic_base)
        titanic_unit = _UnitStub(titanic=True)
        titanic_model.parent_unit = titanic_unit
        titanic_unit.models = [titanic_model]

        game_map = _MapStub([moving_unit, titanic_unit])

        res = is_position_valid_unified_detailed(
            (2.0, 2.0, 0.0),
            moving_model,
            collision_trees={},
            validation_rules={"block_titanic_models": True},
            game_map=game_map,
            is_final_position=True,
        )

        self.assertFalse(res.get("valid"))
        self.assertIn("TITANIC", res.get("reason", ""))

    def test_super_heavy_walker_tall_terrain_battleshock(self):
        from shapely.geometry import Polygon
        from warhammer40k_ai.battlefield.map import TerrainFeature, TerrainType
        from warhammer40k_ai.units.unit import Unit

        class _Datasheet:
            def __init__(self):
                self.name = "Chaos Knight"
                self.faction_data = {"name": "Chaos Knights"}
                self.keywords = ["CHAOS KNIGHTS"]
                self.faction_keywords = ["CHAOS"]
                self.datasheets_unit_composition = [{"description": "1 Test Model"}]
                self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
                self.datasheets_models = [{
                    "M": "10", "T": "10", "Sv": "2", "W": "12",
                    "Ld": "7", "OC": "5",
                    "base_size": "100mm", "inv_sv": "7", "inv_sv_descr": "none",
                }]
                self.datasheets_wargear = []
                self.datasheets_options = [{"description": "none"}]
                self.datasheets_abilities = [{
                    "name": "Super-heavy Walker",
                    "description": "",
                    "type": "Abilities",
                    "parameter": None,
                }]
                self.loadout = "This model is equipped with: nothing"

        unit = Unit(_Datasheet())
        army = SimpleNamespace(player=SimpleNamespace(name="P1", game=SimpleNamespace(turn=1)))
        unit.set_parent_army(army)

        footprint = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
        feature = TerrainFeature(
            TerrainType.WOODS,
            footprint,
            bounding_box={"min": (0.0, 0.0, 0.0), "max": (4.0, 4.0, 6.0)},
        )
        feature.height = 6.0
        game_map = SimpleNamespace(terrain_features=[feature])

        unit.models[0].last_move_path = [(0.0, 0.0, 0.0, 0.0), (3.0, 3.0, 0.0, 0.0)]

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=1):
            unit._apply_super_heavy_walker_terrain_shock(game_map, action="move")

        self.assertTrue(unit.is_battle_shocked())


if __name__ == "__main__":
    unittest.main()
