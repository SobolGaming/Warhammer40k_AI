import unittest


class TestRuinsLowWallTraversal(unittest.TestCase):
    def test_low_ruins_walls_do_not_block_non_infantry_units(self):
        from shapely.geometry import Polygon

        from warhammer40k_ai.battlefield.map import RuinsTerrain, TerrainType
        from warhammer40k_ai.utility.calcs import get_terrain_blocking_polygons, is_terrain_impassable

        # Minimal unit stub: MONSTER-like (cannot traverse walls)
        class _Unit:
            is_flying = False
            is_infantry = False
            is_beast = False
            is_belisarius_cawl = False
            is_imperium_primarch = False
            keywords = ["Monster"]

        u = _Unit()

        footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        low_wall_poly = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])
        tall_wall_poly = Polygon([(4, 0.2), (4.2, 0.2), (4.2, 3.0), (4, 3.0)])

        ruins = RuinsTerrain(
            footprint=footprint,
            walls=[
                {"polygon": low_wall_poly, "z_bottom": 0.0, "z_top": 1.5, "thickness": 0.2},
                {"polygon": tall_wall_poly, "z_bottom": 0.0, "z_top": 4.0, "thickness": 0.2},
            ],
            openings=[],
            floors=[],
            height_map={},
        )
        self.assertEqual(ruins.terrain_type, TerrainType.RUINS)

        # Only tall wall should block
        polys = get_terrain_blocking_polygons(u, ruins)
        self.assertEqual(len(polys), 1)
        self.assertTrue(polys[0].equals(tall_wall_poly))

        # RUINS should still be considered impassable (because there exists a wall > 2")
        self.assertTrue(bool(is_terrain_impassable(u, ruins)))

    def test_ruins_with_only_low_walls_are_not_impassable_for_non_infantry(self):
        from shapely.geometry import Polygon

        from warhammer40k_ai.battlefield.map import RuinsTerrain
        from warhammer40k_ai.utility.calcs import get_terrain_blocking_polygons, is_terrain_impassable

        class _Unit:
            is_flying = False
            is_infantry = False
            is_beast = False
            is_belisarius_cawl = False
            is_imperium_primarch = False
            keywords = ["Monster"]

        u = _Unit()

        footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        low_wall_poly = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])

        ruins = RuinsTerrain(
            footprint=footprint,
            walls=[
                {"polygon": low_wall_poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": 0.2},
            ],
            openings=[],
            floors=[],
            height_map={},
        )

        polys = get_terrain_blocking_polygons(u, ruins)
        self.assertEqual(polys, [])
        self.assertFalse(bool(is_terrain_impassable(u, ruins)))

    def test_ruins_do_not_block_flying_units(self):
        from shapely.geometry import Polygon

        from warhammer40k_ai.battlefield.map import RuinsTerrain
        from warhammer40k_ai.utility.calcs import (
            can_traverse_freely,
            get_terrain_blocking_polygons,
            is_terrain_impassable,
        )

        class _Unit:
            is_flying = True
            is_infantry = False
            is_beast = False
            is_belisarius_cawl = False
            is_imperium_primarch = False
            keywords = []

        u = _Unit()

        footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
        tall_wall_poly = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])

        ruins = RuinsTerrain(
            footprint=footprint,
            walls=[
                {"polygon": tall_wall_poly, "z_bottom": 0.0, "z_top": 5.0, "thickness": 0.2},
            ],
            openings=[],
            floors=[],
            height_map={},
        )

        self.assertEqual(get_terrain_blocking_polygons(u, ruins), [])
        self.assertFalse(bool(is_terrain_impassable(u, ruins)))
        self.assertTrue(can_traverse_freely(u, ruins))


if __name__ == "__main__":
    unittest.main()


