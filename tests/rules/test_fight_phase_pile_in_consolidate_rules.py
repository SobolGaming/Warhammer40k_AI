import os
import sys
import unittest

from shapely.geometry import Polygon

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.battlefield.map import Map, ObjectivePoint
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, clear_enemy_model_cache, clear_collision_caches
from warhammer40k_ai.utility.constants import BASE_CONTACT_EPSILON


class MockDatasheet:
    """Minimal datasheet stub for Unit construction in tests."""

    def __init__(self, name: str, model_count: int = 1):
        self.name = name
        self.faction_data = {"name": "TEST"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_single_model_unit(name: str, faction: str, x: float, y: float) -> Unit:
    unit = Unit(MockDatasheet(name, model_count=1))
    unit.deployed = True
    unit.faction = faction
    unit.models[0].set_location(x, y, 0.0, 0.0)
    return unit


def _place_enemy_at_edge_distance(friendly: Unit, enemy_name: str, enemy_faction: str, edge_dist: float) -> Unit:
    fm = friendly.models[0]
    fr = float(fm.model_base.get_longest_radius())

    enemy = Unit(MockDatasheet(enemy_name, model_count=1))
    enemy.deployed = True
    enemy.faction = enemy_faction
    er = float(enemy.models[0].model_base.get_longest_radius())

    # Put enemy on +X axis with desired edge-to-edge distance.
    # center_dist = fr + er + edge_dist
    center_dist = fr + er + edge_dist
    enemy.models[0].set_location(fm.model_base.x + center_dist, fm.model_base.y, 0.0, 0.0)
    return enemy


def unified_pathfinding(
    model,
    target,
    movement_type,
    max_distance,
    game_map,
    target_unit=None,
    target_units=None,
    moved_models_in_unit=None,
):
    if len(target) == 2:
        target_3d = (float(target[0]), float(target[1]), float(model.model_base.z))
    else:
        target_3d = (float(target[0]), float(target[1]), float(target[2]))
    return plan_model_path(
        PathQuery(
            model=model,
            target=target_3d,
            movement_type=movement_type,
            max_distance=float(max_distance),
            game_map=game_map,
            target_unit=target_unit,
            target_units=tuple(target_units or ()),
            moved_models_in_unit=tuple(moved_models_in_unit or ()),
        )
    ).to_legacy_dict()


class TestPileInAndConsolidateRules(unittest.TestCase):
    def setUp(self):
        # These caches are global and keyed by `id(game_map)` + spatial params.
        # Python can reuse object ids across tests, which can cause stale collision
        # geometry to be reused unless we clear caches explicitly.
        clear_enemy_model_cache()
        clear_collision_caches()
        self.game_map = Map(60, 44)

    def test_pile_in_and_consolidate_apply_pivot_cost(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        pile_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=friendly)
        consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=friendly)
        self.assertTrue(pile_rules.get("apply_pivot_cost"))
        self.assertTrue(consolidate_rules.get("apply_pivot_cost"))

    def test_pile_in_must_end_closer_to_closest_enemy(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=3.2)  # >3 so base contact not required
        self.game_map.units = [friendly, enemy]

        model = friendly.models[0]

        # Zero-distance pile-in should fail (not closer)
        res_same = unified_pathfinding(
            model=model,
            target=(model.model_base.x, model.model_base.y, 0.0),
            movement_type=MovementType.PILE_IN,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertFalse(res_same["valid"], res_same.get("reason"))

        # Moving 3" towards enemy should be valid
        res = unified_pathfinding(
            model=model,
            target=(model.model_base.x + 3.0, model.model_base.y, 0.0),
            movement_type=MovementType.PILE_IN,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res["valid"], res.get("reason"))

    def test_pile_in_requires_base_contact_when_possible(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=2.5)  # <=3 means base contact is achievable
        self.game_map.units = [friendly, enemy]

        model = friendly.models[0]
        fr = float(model.model_base.get_longest_radius())
        er = float(enemy.models[0].model_base.get_longest_radius())
        enemy_x = enemy.models[0].model_base.x

        # End 0.5" away (closer, but not base contact) -> invalid
        target_x_not_contact = enemy_x - (fr + er + 0.5)
        res_not_contact = unified_pathfinding(
            model=model,
            target=(target_x_not_contact, model.model_base.y, 0.0),
            movement_type=MovementType.PILE_IN,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertFalse(res_not_contact["valid"], res_not_contact.get("reason"))

        # End within BASE_CONTACT_EPSILON -> valid
        target_x_contact = enemy_x - (fr + er + (BASE_CONTACT_EPSILON / 2.0))
        res_contact = unified_pathfinding(
            model=model,
            target=(target_x_contact, model.model_base.y, 0.0),
            movement_type=MovementType.PILE_IN,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res_contact["valid"], res_contact.get("reason"))

    def test_consolidate_requires_engagement_when_possible(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        # Edge distance 3.5 -> engagement is achievable (<= 3 + 1)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=3.5)
        self.game_map.units = [friendly, enemy]

        model = friendly.models[0]
        fr = float(model.model_base.get_longest_radius())
        er = float(enemy.models[0].model_base.get_longest_radius())
        enemy_x = enemy.models[0].model_base.x

        # Move closer but still not in engagement (edge 2.0) -> invalid
        target_x_not_engaged = enemy_x - (fr + er + 2.0)
        res_not_engaged = unified_pathfinding(
            model=model,
            target=(target_x_not_engaged, model.model_base.y, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertFalse(res_not_engaged["valid"], res_not_engaged.get("reason"))

        # End in engagement range (edge 0.5) -> valid
        target_x_engaged = enemy_x - (fr + er + 0.5)
        res_engaged = unified_pathfinding(
            model=model,
            target=(target_x_engaged, model.model_base.y, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res_engaged["valid"], res_engaged.get("reason"))

    def test_consolidate_requires_base_contact_when_possible(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=2.5)  # base contact achievable
        self.game_map.units = [friendly, enemy]

        model = friendly.models[0]
        fr = float(model.model_base.get_longest_radius())
        er = float(enemy.models[0].model_base.get_longest_radius())
        enemy_x = enemy.models[0].model_base.x

        # In engagement but not base contact -> invalid
        target_x_not_contact = enemy_x - (fr + er + 0.5)
        res_not_contact = unified_pathfinding(
            model=model,
            target=(target_x_not_contact, model.model_base.y, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertFalse(res_not_contact["valid"], res_not_contact.get("reason"))

        # Base contact -> valid
        target_x_contact = enemy_x - (fr + er + (BASE_CONTACT_EPSILON / 2.0))
        res_contact = unified_pathfinding(
            model=model,
            target=(target_x_contact, model.model_base.y, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res_contact["valid"], res_contact.get("reason"))

    def test_consolidate_objective_fallback_when_no_engagement_possible(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        # Enemy too far to reach engagement with a 3" consolidate (edge 6 > 4)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=6.0)
        self.game_map.units = [friendly, enemy]

        # Objective marker at (15, 10) with 3" control radius
        self.game_map.objectives = [ObjectivePoint(15.0, 10.0, 0.0, control_radius=3.0)]

        model = friendly.models[0]

        # Move 2" toward objective: should end within objective range and be valid
        res_obj = unified_pathfinding(
            model=model,
            target=(12.0, 10.0, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res_obj["valid"], res_obj.get("reason"))

    def test_consolidate_objective_fallback_uses_control_region_geometry(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=6.0)
        self.game_map.units = [friendly, enemy]
        self.game_map.objectives = [
            ObjectiveSite.terrain_footprint(
                footprint=Polygon([(12.5, 8.0), (16.5, 8.0), (16.5, 12.0), (12.5, 12.0)])
            )
        ]

        model = friendly.models[0]

        res_obj = unified_pathfinding(
            model=model,
            target=(12.0, 10.0, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertTrue(res_obj["valid"], res_obj.get("reason"))

    def test_consolidate_cannot_use_objective_if_engagement_possible(self):
        friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
        enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=3.5)  # engagement possible
        self.game_map.units = [friendly, enemy]
        self.game_map.objectives = [ObjectivePoint(15.0, 10.0, 0.0, control_radius=3.0)]

        model = friendly.models[0]

        # A move that heads toward objective but does NOT end in engagement should be invalid
        res = unified_pathfinding(
            model=model,
            target=(12.0, 10.0, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=self.game_map,
        )
        self.assertFalse(res["valid"], res.get("reason"))


if __name__ == '__main__':
    unittest.main()
