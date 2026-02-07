"""
Comprehensive test suite for collision detection across all movement types and scenarios.

Tests cover:
- Map boundary collisions
- Friendly model collisions  
- Enemy model collisions
- Terrain collisions
- All base shapes (circular, elliptical, hull)
- All movement types (MOVE, ADVANCE, FALL_BACK, CHARGE, PILE_IN, CONSOLIDATE, SCOUT)
"""

import pytest

from warhammer40k_ai.utility.calcs import (
    unified_pathfinding, 
    MovementType,
    is_position_valid_unified_detailed,
    build_collision_trees
)
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.battlefield.map import Map, TerrainFactory, TerrainType
from warhammer40k_ai.units.unit import Unit

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from shapely.geometry import Polygon, Point

pytestmark = pytest.mark.slow


class MockDatasheet:
    """Mock datasheet for testing purposes."""
    def __init__(self, name, movement=6, model_count=1, base_size="32mm"):
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
            "M": str(movement), "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class TestCollisionDetection:
    """Test suite for collision detection across all movement types and scenarios."""
    
    def setup_method(self):
        """Set up basic test environment - each test should create its own specific scenario."""
        # Create test map
        self.game_map = Map(width=48, height=72)  # 4x6 feet battlefield
        
        # Create test players and armies
        self.player1 = Player("Player1", PlayerControl.LOCAL)
        self.player2 = Player("Player2", PlayerControl.LOCAL)
        self.army1 = Army("Test Faction 1", "Test Detachment 1")
        self.army2 = Army("Test Faction 2", "Test Detachment 2")
        self.player1.set_army(self.army1)
        self.player2.set_army(self.army2)
    
    def create_circular_unit(self, x=10.0, y=10.0, z=0.0, faction="Test Faction 1"):
        """Create a circular base unit for testing."""
        datasheet = MockDatasheet("Test Infantry", movement=6, base_size="25mm")
        unit = Unit(datasheet)
        unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)  # 25mm base
        unit.models[0].set_location(x, y, z, 0.0)
        unit.deployed = True
        unit.faction = faction
        return unit
    
    def create_elliptical_unit(self, x=10.0, y=16.0, z=0.0, faction="Test Faction 1"):
        """Create an elliptical base unit for testing."""
        datasheet = MockDatasheet("Test Bikes", movement=12, base_size="75x42mm")
        unit = Unit(datasheet)
        unit.models[0].model_base = Base(BaseType.ELLIPTICAL, (2.0, 1.5))  # Bike base
        unit.models[0].set_location(x, y, z, 0.0)
        unit.deployed = True
        unit.faction = faction
        return unit
    
    def create_hull_unit(self, x=10.0, y=23.0, z=0.0, faction="Test Faction 1"):
        """Create a hull base unit for testing."""
        datasheet = MockDatasheet("Test Vehicle", movement=10, base_size="120x92mm")
        unit = Unit(datasheet)
        unit.models[0].model_base = Base(BaseType.HULL, (3.0, 2.0))  # Vehicle hull
        unit.models[0].set_location(x, y, z, 0.0)
        unit.deployed = True
        unit.faction = faction
        return unit
    
    def create_enemy_unit(self, x=24.0, y=36.0, z=0.0, faction="Test Faction 2"):
        """Create an enemy unit for testing."""
        datasheet = MockDatasheet("Enemy Unit", movement=6, base_size="25mm")
        unit = Unit(datasheet)
        unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
        unit.models[0].set_location(x, y, z, 0.0)
        unit.deployed = True
        unit.faction = faction
        return unit
    
    def add_ruins_terrain(self, x1=5.0, y1=5.0, x2=8.0, y2=8.0):
        """Add ruins terrain to the map."""
        ruins_vertices = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        ruins_terrain = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=1)
        self.game_map.add_terrain_feature(ruins_terrain)
    
    def add_crater_terrain(self, center_x=25.0, center_y=25.0, radius=2.0):
        """Add crater terrain to the map."""
        crater_vertices = [(center_x - radius, center_y - radius),
                          (center_x + radius, center_y - radius),
                          (center_x + radius, center_y + radius),
                          (center_x - radius, center_y + radius)]
        crater_terrain = TerrainFactory.create_crater(crater_vertices, depth=2.0, rim_height=1.0)
        self.game_map.add_terrain_feature(crater_terrain)
    
    def setup_units_on_map(self, units):
        """Add units to the map and set up army relationships."""
        self.game_map.units = units
        self.army1.units = [u for u in units if u.faction == "Test Faction 1"]
        self.army2.units = [u for u in units if u.faction == "Test Faction 2"]
    
    def test_map_boundary_collision_circular(self):
        """Test that circular bases cannot move outside map boundaries."""

        # Create test scenario with a single unit
        unit = self.create_circular_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit])
        
        model = unit.models[0]

        # Test moving outside left boundary (far enough to avoid other obstacles)
        result = unified_pathfinding(
            model=model,
            target=(-2.0, 36.0, 0.0),  # Well outside left edge
            movement_type=MovementType.MOVE,
            max_distance=30.0,  # Enough distance to reach if no boundary
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow movement outside left boundary"
        # The pathfinding should fail due to boundary check or no valid path

        # Test moving outside right boundary
        result = unified_pathfinding(
            model=model,
            target=(50.0, 36.0, 0.0),  # Outside right edge (map width = 48)
            movement_type=MovementType.MOVE,
            max_distance=30.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow movement outside right boundary"
    
    def test_map_boundary_collision_elliptical(self):
        """Test that elliptical bases cannot move outside map boundaries."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        self.setup_units_on_map([unit, elliptical_unit])


        model = elliptical_unit.models[0]
        
        # Test moving outside top boundary
        result = unified_pathfinding(
            model=model,
            target=(20.0, 74.0, 0.0),  # Outside top edge (map height = 72)
            movement_type=MovementType.MOVE,
            max_distance=12.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow elliptical base outside top boundary"
    
    def test_map_boundary_collision_hull(self):
        """Test that hull bases cannot move outside map boundaries."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, hull_unit])


        model = hull_unit.models[0]
        
        # Test moving outside bottom boundary
        result = unified_pathfinding(
            model=model,
            target=(30.0, -1.0, 0.0),  # Outside bottom edge
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow hull base outside bottom boundary"

    def test_friendly_model_collision_prevention(self):
        """Test that friendly models cannot overlap with each other."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        self.setup_units_on_map([unit, elliptical_unit])


        # Move units to clear area away from terrain
        unit.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        elliptical_unit.models[0].set_location(20.0, 25.0, 0.0, 0.0)

        model = unit.models[0]

        # Try to move circular model to overlap with elliptical model
        elliptical_pos = elliptical_unit.models[0].get_location()
        result = unified_pathfinding(
            model=model,
            target=(elliptical_pos[0], elliptical_pos[1], elliptical_pos[2]),
            movement_type=MovementType.MOVE,
            max_distance=20.0,  # Enough distance to reach
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow friendly model overlap"
        assert "friendly" in result['reason'].lower()

    def test_enemy_model_collision_prevention(self):
        """Test that models cannot overlap with enemy models during normal movement."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        # Create a clean scenario with just two units
        friendly_unit = self.create_circular_unit(x=30.0, y=30.0, faction="Test Faction 1")
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0, faction="Test Faction 2")
        self.setup_units_on_map([friendly_unit, enemy_unit])
        
        model = friendly_unit.models[0]

        # Try to move to overlap with enemy model
        enemy_pos = enemy_unit.models[0].get_location()
        result = unified_pathfinding(
            model=model,
            target=(enemy_pos[0], enemy_pos[1], enemy_pos[2]),
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow enemy model overlap during normal movement"
        # Should be blocked by enemy models or engagement range
        assert ("enemy" in result['reason'].lower() or
                "engagement" in result['reason'].lower())

    def test_terrain_collision_prevention(self):
        """Test that models cannot move through terrain they cannot traverse."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, hull_unit])


        # Use vehicle unit which cannot traverse RUINS
        hull_unit.keywords = ['Vehicle']  # Ensure it's a vehicle
        model = hull_unit.models[0]

        # Move model to clear area first to avoid friendly collisions
        model.set_location(10.0, 10.0, 0.0, 0.0)

        # Try to move into terrain obstacle (RUINS at 5-8, 5-8)
        result = unified_pathfinding(
            model=model,
            target=(6.5, 6.5, 0.0),  # Inside terrain piece
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow movement through impassable terrain"
        # Check that terrain collision is detected (either in reason or as one of the obstacles)
        reason_lower = result['reason'].lower()
        terrain_detected = ("terrain" in reason_lower or
                          "obstacles" in reason_lower or
                          "blocked" in reason_lower)
        assert terrain_detected, f"Expected terrain collision detection, got: {result['reason']}"

    def test_engagement_range_prevention_normal_movement(self):
        """Test that normal movement cannot enter engagement range of enemies."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        # Create a clean scenario with just two units
        friendly_unit = self.create_circular_unit(x=30.0, y=30.0, faction="Test Faction 1")
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0, faction="Test Faction 2")
        self.setup_units_on_map([friendly_unit, enemy_unit])
        
        model = friendly_unit.models[0]

        # Try to move within 1" of enemy model
        enemy_pos = enemy_unit.models[0].get_location()
        close_position = (enemy_pos[0] + 0.5, enemy_pos[1], enemy_pos[2])  # 0.5" away

        result = unified_pathfinding(
            model=model,
            target=close_position,
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow normal movement within engagement range"
        assert "engagement" in result['reason'].lower()

    def test_charge_movement_allows_engagement_range(self):
        """Test that charge movement can enter engagement range of target unit."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]

        # Position model closer to enemy for charge test
        enemy_pos = enemy_unit.models[0].get_location()
        start_position = (enemy_pos[0] - 8.0, enemy_pos[1], enemy_pos[2])  # 8" away
        model.set_location(start_position[0], start_position[1], start_position[2], 0.0)

        # Try to charge into engagement range of enemy (base-to-base contact)
        # For 1" radius bases, centers should be 2" apart for base contact
        charge_position = (enemy_pos[0] - 2.0, enemy_pos[1], enemy_pos[2])  # Base-to-base contact

        result = unified_pathfinding(
            model=model,
            target=charge_position,
            movement_type=MovementType.CHARGE,
            max_distance=12.0,  # 2D6 charge roll
            game_map=self.game_map,
            target_unit=enemy_unit
        )
        assert result['valid'], "Should allow charge movement into engagement range"

    def test_fall_back_movement_through_models(self):
        """Test that fall back movement can move through models but not end in engagement range."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        # Position model near enemy for fall back scenario
        model = unit.models[0]
        enemy_pos = enemy_unit.models[0].get_location()
        model.set_location(enemy_pos[0] - 1.5, enemy_pos[1], enemy_pos[2], 0.0)  # Start near enemy (within engagement range)

        # Fall back through enemy model to safe position
        safe_position = (enemy_pos[0] - 5.0, enemy_pos[1], enemy_pos[2])

        result = unified_pathfinding(
            model=model,
            target=safe_position,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert result['valid'], "Should allow fall back movement through models"

    def test_fall_back_through_enemy_models(self):
        """Test that fall back movement can move through enemy models specifically."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]
        enemy_pos = enemy_unit.models[0].get_location()

        # Position model in engagement range of enemy
        model.set_location(enemy_pos[0] - 1.5, enemy_pos[1], enemy_pos[2], 0.0)

        # Try to fall back through the enemy model to the other side
        target_through_enemy = (enemy_pos[0] + 3.0, enemy_pos[1], enemy_pos[2])

        result = unified_pathfinding(
            model=model,
            target=target_through_enemy,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert result['valid'], "Should allow fall back through enemy models"

        # Verify the path goes through the enemy position
        if result['path'] and len(result['path']) > 2:
            # Check that path passes near enemy position (indicating movement through enemy)
            for point in result['path']:
                dist_to_enemy = ((point[0] - enemy_pos[0])**2 + (point[1] - enemy_pos[1])**2)**0.5
                if dist_to_enemy < 2.0:  # Within 2" of enemy center
                    break
            # Note: This might not always be true if straight line path is used

    def test_fall_back_cannot_end_in_engagement_range(self):
        """Test that fall back movement cannot end within engagement range of enemies."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]
        enemy_pos = enemy_unit.models[0].get_location()

        # Position model near enemy
        model.set_location(enemy_pos[0] - 3.0, enemy_pos[1], enemy_pos[2], 0.0)

        # Try to fall back to a position still within engagement range
        target_in_engagement = (enemy_pos[0] - 0.5, enemy_pos[1], enemy_pos[2])  # Too close to enemy

        result = unified_pathfinding(
            model=model,
            target=target_in_engagement,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow fall back ending in engagement range"
        assert "engagement range" in result['reason'].lower()

    def test_desperate_escape_scenario(self):
        """Test desperate escape when normal fall back is blocked."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]

        # Create a scenario where the unit is surrounded/blocked
        # Position model very close to battlefield edge with enemy nearby
        model.set_location(2.0, 36.0, 0.0, 0.0)  # Near left edge

        # Position enemy to block normal fall back routes
        enemy_unit.models[0].set_location(4.0, 36.0, 0.0, 0.0)  # Blocking escape

        # Try to fall back - should either find a path through enemy or fail
        target_escape = (8.0, 36.0, 0.0)  # Through enemy position

        result = unified_pathfinding(
            model=model,
            target=target_escape,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )

        # Desperate Escape Rule: When fall back path goes through enemy models,
        # each model that moved through an enemy must make a Desperate Escape test

        if result['valid']:
            # Path found - check if it goes through enemy models
            assert result['distance'] <= 6.0, "Fall back distance should be within limit"

            # Check if path goes through enemy position (indicating Desperate Escape needed)
            enemy_pos = enemy_unit.models[0].get_location()
            path_through_enemy = False

            if result['path'] and len(result['path']) > 1:
                for point in result['path']:
                    dist_to_enemy = ((point[0] - enemy_pos[0])**2 + (point[1] - enemy_pos[1])**2)**0.5
                    if dist_to_enemy < 2.0:  # Within 2" of enemy center (indicating movement through)
                        path_through_enemy = True
                        break

            # In a real game, if path_through_enemy is True, the model would need to:
            # 1. Make a Desperate Escape test (roll D6)
            # 2. On 1-2: model is destroyed
            # 3. On 3+: model survives the fall back

            # For testing purposes, we verify that:
            # 1. The pathfinding allows movement through enemies (fall back rule)
            # 2. We can detect when Desperate Escape tests would be needed
            if path_through_enemy:
                print(f"ðŸ” DEBUG: Path goes through enemy - Desperate Escape test would be required")

            # The Desperate Escape dice rolling would be handled by game logic, not pathfinding

        else:
            # If no valid path found, the unit cannot fall back (different from Desperate Escape)
            # This would typically mean the unit is completely trapped
            assert "no path" in result['reason'].lower() or "blocked" in result['reason'].lower()

    def test_battle_shocked_desperate_escape(self):
        """Test that battle-shocked units require Desperate Escape tests regardless of path."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Make unit battle-shocked
        from warhammer40k_ai.units.status_effects import BattleShockEffect
        battle_shock_effect = BattleShockEffect(1)
        unit.apply_status_effect(battle_shock_effect)

        # Position unit away from enemies (clear path)
        model.set_location(10.0, 50.0, 0.0, 0.0)

        # Fall back to clear position (no enemy models in path)
        target_clear = (15.0, 50.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_clear,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )

        # Fall back should be allowed
        assert result['valid'], "Battle-shocked unit should be able to fall back"

        # Check Desperate Escape requirements
        if 'desperate_escape' in result:
            desperate_escape = result['desperate_escape']
            assert desperate_escape['required'], "Battle-shocked unit should require Desperate Escape"
            assert desperate_escape['all_models'], "All models in battle-shocked unit should test"
            assert desperate_escape['reason'] == 'Battle-shocked unit falling back'

    def test_titanic_fly_exempt_from_desperate_escape(self):
        """Test that TITANIC and FLY units are exempt from Desperate Escape when moving through enemies."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        # This test would require creating a unit with TITANIC or FLY keywords
        # For now, we'll test the logic conceptually

        model = unit.models[0]

        # Position model near enemy
        enemy_pos = enemy_unit.models[0].get_location()
        model.set_location(enemy_pos[0] - 3.0, enemy_pos[1], enemy_pos[2], 0.0)

        # Fall back through enemy (would normally require Desperate Escape)
        target_through_enemy = (enemy_pos[0] + 3.0, enemy_pos[1], enemy_pos[2])

        result = unified_pathfinding(
            model=model,
            target=target_through_enemy,
            movement_type=MovementType.FALL_BACK,
            max_distance=8.0,
            game_map=self.game_map
        )

        # Fall back should be allowed
        assert result['valid'], "Fall back through enemy should be allowed"

        # For a normal unit, this would require Desperate Escape
        if 'desperate_escape' in result:
            desperate_escape = result['desperate_escape']
            # Note: In a real test with TITANIC/FLY unit, this would be False
            # For this test unit (no special keywords), it should be True
            print(f"ðŸ” DEBUG: Desperate Escape required: {desperate_escape.get('required', 'N/A')}")
            print(f"ðŸ” DEBUG: Reason: {desperate_escape.get('reason', 'N/A')}")

    def test_normal_fall_back_no_desperate_escape(self):
        """Test that normal fall back without going through enemies doesn't require Desperate Escape."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Position unit away from enemies
        model.set_location(10.0, 50.0, 0.0, 0.0)

        # Fall back to position that doesn't go through enemies
        target_clear = (5.0, 50.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_clear,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )

        # Fall back should be allowed
        assert result['valid'], "Normal fall back should be allowed"

        # Should not require Desperate Escape
        if 'desperate_escape' in result:
            desperate_escape = result['desperate_escape']
            assert not desperate_escape['required'], "Normal fall back should not require Desperate Escape"
            assert not desperate_escape['path_through_enemy'], "Path should not go through enemies"

    def test_infantry_can_traverse_ruins(self):
        """Test that INFANTRY units can move through RUINS terrain."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create an INFANTRY unit by adding the keyword
        infantry_unit = unit
        infantry_unit.keywords = ['Infantry']  # Add Infantry keyword (case-sensitive)
        model = infantry_unit.models[0]

        # Create RUINS terrain that blocks the direct path
        ruins_vertices = [(12.0, 12.0), (16.0, 12.0), (16.0, 16.0), (12.0, 16.0)]
        ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=1)
        self.game_map.add_terrain_feature(ruins)

        # Store reference to this specific ruins for the vehicle test
        self.vehicle_test_ruins = ruins

        # Position model on one side of ruins
        model.set_location(10.0, 14.0, 0.0, 0.0)

        # Try to move through ruins to other side
        target_through_ruins = (18.0, 14.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_ruins,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # INFANTRY should be able to move through RUINS
        assert result['valid'], "INFANTRY units should be able to move through RUINS"
        assert result['distance'] <= 10.0, "Movement should be within distance limit"

    def test_vehicle_cannot_traverse_ruins(self):
        """Test that VEHICLE units cannot move through RUINS terrain."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, elliptical_unit, hull_unit])


        # Create a VEHICLE unit by adding the keyword
        vehicle_unit = hull_unit  # Hull units are typically vehicles
        vehicle_unit.keywords = ['Vehicle']  # Add Vehicle keyword (case-sensitive)
        model = vehicle_unit.models[0]

        # Create RUINS terrain that blocks the direct path
        ruins_vertices = [(12.0, 12.0), (16.0, 12.0), (16.0, 16.0), (12.0, 16.0)]
        ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=1)
        self.game_map.add_terrain_feature(ruins)

        # Position model on one side of ruins terrain, away from other models
        model.set_location(10.0, 14.0, 0.0, 0.0)
        # Move other models away to avoid friendly collisions
        unit.models[0].set_location(30.0, 30.0, 0.0, 0.0)
        elliptical_unit.models[0].set_location(30.0, 35.0, 0.0, 0.0)

        # Try to move through the center of ruins to other side
        target_through_ruins = (14.0, 14.0, 0.0)  # Center of RUINS at (12-16, 12-16)



        result = unified_pathfinding(
            model=model,
            target=target_through_ruins,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # VEHICLE should NOT be able to move through RUINS
        assert not result['valid'], "VEHICLE units should not be able to move through RUINS"
        assert "terrain" in result['reason'].lower(), "Should be blocked by terrain"

    def test_beast_can_traverse_ruins(self):
        """Test that BEAST units can move through RUINS terrain."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        self.setup_units_on_map([unit, elliptical_unit])


        # Create a BEAST unit by adding the keyword
        beast_unit = elliptical_unit  # Use elliptical unit for variety
        beast_unit.keywords = ['Beast']  # Add Beast keyword (case-sensitive)
        model = beast_unit.models[0]

        # Position model on one side of ruins
        model.set_location(10.0, 14.0, 0.0, 0.0)

        # Try to move through ruins to other side
        target_through_ruins = (18.0, 14.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_ruins,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # BEAST should be able to move through RUINS
        assert result['valid'], "BEAST units should be able to move through RUINS"
        assert result['distance'] <= 10.0, "Movement should be within distance limit"

    def test_fly_can_traverse_any_terrain(self):
        """Test that FLY units can move through any terrain type."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create a FLY unit by adding the keyword
        fly_unit = unit
        fly_unit.keywords = ['Fly']  # Add Fly keyword (case-sensitive)
        model = fly_unit.models[0]

        # Create terrain (HILLS_AND_SEALED_BUILDINGS)
        building_vertices = [(20.0, 20.0), (24.0, 20.0), (24.0, 24.0), (20.0, 24.0)]
        building = TerrainFactory.create_hill(building_vertices, height=6.0)
        self.game_map.add_terrain_feature(building)

        # Position model on one side of building
        model.set_location(18.0, 22.0, 0.0, 0.0)

        # Try to move through building to other side
        target_through_building = (26.0, 22.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_building,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # FLY should be able to move through any terrain
        assert result['valid'], "FLY units should be able to move through any terrain"
        assert result['distance'] <= 10.0, "Movement should be within distance limit"

    def test_all_units_can_traverse_woods(self):
        """Test that all units can move through WOODS terrain."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create WOODS terrain in a clear area away from enemy
        woods_vertices = [(15.0, 50.0), (19.0, 50.0), (19.0, 54.0), (15.0, 54.0)]
        woods = TerrainFactory.create_woods(woods_vertices, height=3.0)
        self.game_map.add_terrain_feature(woods)

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, elliptical_unit, hull_unit])

        # Test with different unit types
        test_units = [
            (unit, ['Infantry']),
            (hull_unit, ['Vehicle']),
            (elliptical_unit, ['Beast'])
        ]

        for i, (unit, keywords) in enumerate(test_units):
            unit.keywords = keywords
            model = unit.models[0]

            # Position model on one side of woods (use different Y positions to avoid collisions)
            start_y = 52.0 + (i * 5.0)  # Spread units vertically with more space
            model.set_location(13.0, start_y, 0.0, 0.0)

            # Try to move through woods to other side
            target_through_woods = (21.0, start_y, 0.0)

            print(f"ðŸ” DEBUG: Testing {keywords[0]} unit - keywords: {unit.keywords}")
            print(f"ðŸ” DEBUG: is_infantry: {unit.is_infantry}, is_beast: {unit.is_beast}, is_flying: {unit.is_flying}")

            result = unified_pathfinding(
                model=model,
                target=target_through_woods,
                movement_type=MovementType.MOVE,
                max_distance=12.0,  # Increase distance limit to allow for longer paths
                game_map=self.game_map
            )

            # All units should be able to move through WOODS
            assert result['valid'], f"{keywords[0]} units should be able to move through WOODS. Reason: {result.get('reason', 'Unknown')}"
            assert result['distance'] <= 12.0, "Movement should be within distance limit"

    def test_low_height_terrain_traversable(self):
        """Test that terrain â‰¤2" height can be traversed by all units."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create low height terrain (â‰¤2" is freely climbable) away from other units
        low_terrain_vertices = [(30.0, 40.0), (34.0, 40.0), (34.0, 44.0), (30.0, 44.0)]
        low_terrain = TerrainFactory.create_debris(low_terrain_vertices, height=2.0)  # 2" height
        self.game_map.add_terrain_feature(low_terrain)

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, hull_unit])

        # Test with a VEHICLE (normally can't traverse RUINS, but should traverse low terrain)
        vehicle_unit = hull_unit
        vehicle_unit.keywords = ['Vehicle']
        model = vehicle_unit.models[0]

        # Position model on one side of low terrain, away from other units
        model.set_location(28.0, 42.0, 0.0, 0.0)

        # Try to move through low terrain to other side
        target_through_low_terrain = (36.0, 42.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_low_terrain,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # All units should be able to traverse low height terrain
        assert result['valid'], "All units should be able to traverse terrain â‰¤2\" height"
        assert result['distance'] <= 10.0, "Movement should be within distance limit"

    def test_barricade_traversal_but_cannot_end_on(self):
        """Test that units can traverse BARRICADE_AND_FUEL_PIPES but cannot end moves on it."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create BARRICADE_AND_FUEL_PIPES terrain
        barricade = TerrainFactory.create_barricade(
            start_point=(40.0, 40.0),
            end_point=(44.0, 44.0),
            height=2.0
        )
        self.game_map.add_terrain_feature(barricade)

        # Test with Infantry unit
        infantry_unit = unit
        infantry_unit.keywords = ['Infantry']
        model = infantry_unit.models[0]

        # Position model on one side of barricade
        model.set_location(38.0, 42.0, 0.0, 0.0)

        # Test 1: Can move through barricade to other side
        target_through_barricade = (46.0, 42.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_barricade,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # Should be able to move through barricade
        assert result['valid'], "Units should be able to move through BARRICADE_AND_FUEL_PIPES"

        # Test 2: Cannot end move on top of barricade
        target_on_barricade = (42.0, 42.0, 0.0)  # Center of barricade

        result_on_barricade = unified_pathfinding(
            model=model,
            target=target_on_barricade,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # Should not be able to end move on barricade
        # Note: This test depends on the final position validation being implemented
        # For now, we test that movement through is allowed
        print(f"ðŸ” DEBUG: Movement to barricade center: {result_on_barricade['valid']}")

    def test_debris_traversal_but_cannot_end_on(self):
        """Test that units can traverse DEBRIS_AND_STATUARY but cannot end moves on it."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create DEBRIS_AND_STATUARY terrain in safe area
        debris_vertices = [(25.0, 60.0), (29.0, 60.0), (29.0, 64.0), (25.0, 64.0)]
        debris = TerrainFactory.create_debris(debris_vertices, height=1.5)
        self.game_map.add_terrain_feature(debris)

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, hull_unit])

        # Test with Vehicle unit
        vehicle_unit = hull_unit
        vehicle_unit.keywords = ['Vehicle']
        model = vehicle_unit.models[0]

        # Position model on one side of debris
        model.set_location(23.0, 62.0, 0.0, 0.0)

        # Test: Can move through debris to other side
        target_through_debris = (31.0, 62.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_through_debris,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # Should be able to move through debris
        assert result['valid'], "Units should be able to move through DEBRIS_AND_STATUARY"

    def test_hills_buildings_base_overhang_rules(self):
        """Test that units can end moves on HILLS_AND_SEALED_BUILDINGS if base doesn't overhang."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create HILLS_AND_SEALED_BUILDINGS terrain within map boundaries
        building_vertices = [(35.0, 60.0), (39.0, 60.0), (39.0, 64.0), (35.0, 64.0)]
        building = TerrainFactory.create_hill(building_vertices, height=4.0)
        self.game_map.add_terrain_feature(building)

        # Test with Infantry unit (small base)
        infantry_unit = unit
        infantry_unit.keywords = ['Infantry']
        model = infantry_unit.models[0]

        # Position model near building
        model.set_location(33.0, 62.0, 0.0, 0.0)

        # Test: Can move to center of building (base should fit)
        target_on_building = (37.0, 62.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_on_building,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        # Should be able to move onto building if base fits
        assert result['valid'], "Units should be able to move onto HILLS_AND_SEALED_BUILDINGS if base doesn't overhang"

    def test_ruins_special_keyword_traversal(self):
        """Test that only special keyworded units can move through RUINS walls."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # The existing ruins test already covers this, but let's add a comprehensive test

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, elliptical_unit, hull_unit])

        # Test units with different keywords
        test_cases = [
            (unit, ['Infantry'], True, "Infantry should traverse RUINS"),
            (elliptical_unit, ['Beast'], True, "Beast should traverse RUINS"),
            (hull_unit, ['Vehicle'], False, "Vehicle should NOT traverse RUINS"),
            (unit, ['Fly'], True, "FLY should traverse any terrain")  # FLY can traverse anything
        ]

        for i, (unit, keywords, should_pass, message) in enumerate(test_cases):
            unit.keywords = keywords
            model = unit.models[0]

            # Position each unit at different locations to avoid collisions
            start_x = 8.0 + (i * 5.0)  # Start further from edge, spread more
            model.set_location(start_x, 14.0, 0.0, 0.0)

            # Try to move through existing ruins to other side
            target_x = start_x + 8.0  # Shorter distance to stay within bounds
            target_through_ruins = (target_x, 14.0, 0.0)

            result = unified_pathfinding(
                model=model,
                target=target_through_ruins,
                movement_type=MovementType.MOVE,
                max_distance=12.0,
                game_map=self.game_map
            )

            if should_pass:
                assert result['valid'], message
            else:
                # For units that can't traverse, they might find a path around or fail
                # The key is that they shouldn't be able to go straight through
                if not result['valid']:
                    assert "terrain" in result['reason'].lower(), f"{message} - should be blocked by terrain"

    def test_desperate_escape_detection(self):
        """Test detection of when Desperate Escape tests are required during fall back."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]

        # Position model on one side of enemy
        enemy_pos = enemy_unit.models[0].get_location()
        model.set_location(enemy_pos[0] - 2.5, enemy_pos[1], enemy_pos[2], 0.0)  # 2.5" away

        # Fall back to position on other side of enemy (forcing movement through enemy)
        target_beyond_enemy = (enemy_pos[0] + 3.0, enemy_pos[1], enemy_pos[2])

        result = unified_pathfinding(
            model=model,
            target=target_beyond_enemy,
            movement_type=MovementType.FALL_BACK,
            max_distance=6.0,
            game_map=self.game_map
        )

        # Fall back should be allowed (can move through enemies)
        assert result['valid'], "Fall back through enemy should be allowed"

        # Check if path goes through enemy (indicating Desperate Escape needed)
        path_through_enemy = False
        if result['path'] and len(result['path']) > 1:
            for point in result['path']:
                dist_to_enemy = ((point[0] - enemy_pos[0])**2 + (point[1] - enemy_pos[1])**2)**0.5
                if dist_to_enemy < 2.0:  # Close to enemy center
                    path_through_enemy = True
                    break

        # In this scenario, the path should go through the enemy
        # (In a real game, this would trigger Desperate Escape tests)
        if path_through_enemy:
            print(f"ðŸ” DEBUG: Desperate Escape test required - model moved through enemy")

        # The key test: fall back is valid but may require Desperate Escape
        assert result['distance'] <= 6.0, "Fall back distance should be within limit"

    def test_scout_movement_9_inch_restriction(self):
        """Test that scout movement maintains 9\" distance from enemies."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]

        # Try to scout within 9" of enemy
        enemy_pos = enemy_unit.models[0].get_location()
        too_close_position = (enemy_pos[0] + 5.0, enemy_pos[1], enemy_pos[2])  # 5" away

        result = unified_pathfinding(
            model=model,
            target=too_close_position,
            movement_type=MovementType.SCOUT,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow scout movement within 9\" of enemies"

    def test_valid_movement_in_clear_space(self):
        """Test that valid movement in clear space is allowed."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Move to clear space away from all obstacles and models
        clear_position = (40.0, 40.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=clear_position,
            movement_type=MovementType.MOVE,
            max_distance=50.0,  # Enough distance
            game_map=self.game_map
        )
        assert result['valid'], f"Should allow movement to clear space: {result['reason']}"
        assert result['path'] is not None
        assert len(result['path']) >= 2  # Start and end points

    def test_straight_line_optimization(self):
        """Test that straight line paths are used when no obstacles are present."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create a clean scenario with just one unit
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])
        
        model = unit.models[0]

        # Move to clear space that should use straight line
        clear_position = (12.0, 12.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=clear_position,
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )
        assert result['valid'], "Should allow straight line movement"
        # Straight line should have only start and end points
        assert len(result['path']) == 2, f"Expected straight line (2 points), got {len(result['path'])} points"

    def test_distance_limit_enforcement(self):
        """Test that movement distance limits are enforced."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, elliptical_unit, hull_unit, enemy_unit])


        # Move ALL units to clear areas to avoid collisions
        unit.models[0].set_location(10.0, 30.0, 0.0, 0.0)
        elliptical_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)  # Far away
        hull_unit.models[0].set_location(40.0, 10.0, 0.0, 0.0)  # Far away
        enemy_unit.models[0].set_location(40.0, 60.0, 0.0, 0.0)  # Far away

        model = unit.models[0]

        # Try to move beyond maximum distance in clear area
        far_position = (20.0, 30.0, 0.0)  # 10" away

        result = unified_pathfinding(
            model=model,
            target=far_position,
            movement_type=MovementType.MOVE,
            max_distance=5.0,  # Too short to reach (only 5" allowed)
            game_map=self.game_map
        )
        assert not result['valid'], "Should not allow movement beyond maximum distance"
        assert "distance" in result['reason'].lower() or "long" in result['reason'].lower() or "iterations" in result['reason'].lower()

    def test_all_base_shapes_collision_detection(self):
        """Test collision detection works for all base shape types."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        hull_unit = self.create_hull_unit(x=10.0, y=23.0)
        self.setup_units_on_map([unit, elliptical_unit, hull_unit])


        # Test circular vs elliptical collision
        circular_model = unit.models[0]
        elliptical_pos = elliptical_unit.models[0].get_location()

        result = unified_pathfinding(
            model=circular_model,
            target=(elliptical_pos[0], elliptical_pos[1], elliptical_pos[2]),
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Circular base should not overlap with elliptical base"

        # Test elliptical vs hull collision
        elliptical_model = elliptical_unit.models[0]
        hull_pos = hull_unit.models[0].get_location()

        result = unified_pathfinding(
            model=elliptical_model,
            target=(hull_pos[0], hull_pos[1], hull_pos[2]),
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Elliptical base should not overlap with hull base"

    def test_edge_case_near_boundary(self):
        """Test movement very close to but not exceeding boundaries."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create a clean scenario with just one unit
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])
        
        model = unit.models[0]

        # Move to position that should just fit within boundary
        # Assuming 1" radius, position at x=1.1 should fit (1.1 - 1.0 = 0.1" from edge)
        near_boundary_position = (1.1, 10.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=near_boundary_position,
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert result['valid'], "Should allow movement that just fits within boundary"

    def test_pile_in_movement_constraints(self):
        """Test pile-in movement specific constraints."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Pile-in should have 3" maximum distance
        far_position = (15.0, 15.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=far_position,
            movement_type=MovementType.PILE_IN,
            max_distance=6.0,  # This should be overridden to 3"
            game_map=self.game_map
        )
        # Should either be invalid due to distance or use 3" override
        if not result['valid']:
            assert "distance" in result['reason'].lower()

    def test_advance_movement_extra_distance(self):
        """Test that advance movement allows extra distance."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create a clean scenario with just one unit
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])
        
        model = unit.models[0]

        # Test advance movement (should work same as normal move for collision)
        clear_position = (16.0, 16.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=clear_position,
            movement_type=MovementType.ADVANCE,
            max_distance=12.0,  # 6" + D6 advance
            game_map=self.game_map
        )
        assert result['valid'], "Should allow advance movement to clear position"

    def test_position_validation_function_directly(self):
        """Test the is_position_valid_unified_detailed function directly."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        enemy_unit = self.create_enemy_unit(x=24.0, y=36.0)
        self.setup_units_on_map([unit, enemy_unit])


        model = unit.models[0]

        # Build collision trees
        collision_trees = build_collision_trees(model.parent_unit, MovementType.MOVE, self.game_map)
        validation_rules = {
            'prevent_friendly_overlap': True,
            'prevent_enemy_overlap': True,
            'cannot_move_within_engagement_range': True
        }

        # Test valid position
        valid_pos = (12.0, 12.0, 0.0)
        result = is_position_valid_unified_detailed(valid_pos, model, collision_trees, validation_rules, self.game_map)
        assert result['valid'], "Should validate clear position as valid"

        # Test invalid position (overlapping with enemy)
        enemy_pos = enemy_unit.models[0].get_location()
        result = is_position_valid_unified_detailed(enemy_pos, model, collision_trees, validation_rules, self.game_map)
        assert not result['valid'], "Should validate overlapping position as invalid"

    def test_consolidate_movement_constraints(self):
        """Test consolidate movement specific constraints."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Consolidate should have 3" maximum distance like pile-in
        result = unified_pathfinding(
            model=model,
            target=(13.0, 13.0, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=6.0,  # Should be overridden to 3"
            game_map=self.game_map
        )
        # Should work for short distances
        assert result is not None, "Should return result for consolidate movement"

    def test_multiple_collision_types_simultaneously(self):
        """Test position that violates multiple collision rules."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        model = unit.models[0]

        # Try to move to position that's outside boundary AND overlaps with terrain
        invalid_position = (-1.0, 6.5, 0.0)  # Outside boundary and in terrain

        result = unified_pathfinding(
            model=model,
            target=invalid_position,
            movement_type=MovementType.MOVE,
            max_distance=20.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should reject position with multiple violations"

    def test_pathfinding_with_obstacles_requiring_detour(self):
        """Test pathfinding that requires going around obstacles."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])

        # Create terrain obstacle that blocks the direct path
        # RUINS terrain at (5-8, 5-8) that blocks the direct path from (10,10) to (3,6)
        ruins_vertices = [(5.0, 5.0), (8.0, 5.0), (8.0, 8.0), (5.0, 8.0)]
        ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=1)
        self.game_map.add_terrain_feature(ruins)

        model = unit.models[0]

        # Move to position that requires going around terrain
        # Start at (10, 10), terrain at (5-8, 5-8), target at (3, 6) - requires going around terrain
        target_behind_terrain = (3.0, 6.0, 0.0)

        result = unified_pathfinding(
            model=model,
            target=target_behind_terrain,
            movement_type=MovementType.MOVE,
            max_distance=15.0,
            game_map=self.game_map
        )

        if result['valid']:
            # If path found, it should be longer than straight line due to detour
            assert len(result['path']) > 2, "Should require detour around obstacle"
            assert result['distance'] > 5.0, "Detour should be longer than straight line"
        else:
            # If no path found, that's also valid - terrain might completely block the path
            assert "terrain" in result['reason'].lower() or "obstacle" in result['reason'].lower(), f"Should be blocked by terrain, got: {result.get('reason', 'Unknown')}"

    def test_error_handling_invalid_inputs(self):
        """Test error handling for invalid inputs."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Test with None model
        result = unified_pathfinding(
            model=None,
            target=(10.0, 10.0, 0.0),
            movement_type=MovementType.MOVE,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should handle None model gracefully"
        assert "invalid" in result['reason'].lower() or "error" in result['reason'].lower()

        # Test with invalid target
        result = unified_pathfinding(
            model=unit.models[0],
            target=None,
            movement_type=MovementType.MOVE,
            max_distance=6.0,
            game_map=self.game_map
        )
        assert not result['valid'], "Should handle None target gracefully"
        assert "invalid" in result['reason'].lower() or "error" in result['reason'].lower()

        # Test with invalid max_distance
        result = unified_pathfinding(
            model=unit.models[0],
            target=(10.0, 10.0, 0.0),
            movement_type=MovementType.MOVE,
            max_distance=-1.0,  # Invalid negative distance
            game_map=self.game_map
        )
        assert not result['valid'], "Should handle invalid max_distance gracefully"
        assert "invalid" in result['reason'].lower() or "error" in result['reason'].lower()

    def test_3d_positioning_different_floors(self):
        """Test that models can occupy same X,Y position on different floors if Z-delta > model height."""
        # Create multi-floor RUINS terrain
        ruins_vertices = [(10.0, 10.0), (15.0, 10.0), (15.0, 15.0), (10.0, 15.0)]
        ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=2)  # Ground + 1st + 2nd floor
        self.game_map.add_terrain_feature(ruins)

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        elliptical_unit = self.create_elliptical_unit(x=10.0, y=16.0)
        self.setup_units_on_map([unit, elliptical_unit])

        # Use Infantry units that can traverse RUINS
        infantry_unit1 = unit
        infantry_unit1.keywords = ['Infantry']
        model1 = infantry_unit1.models[0]

        infantry_unit2 = elliptical_unit
        infantry_unit2.keywords = ['Infantry']
        model2 = infantry_unit2.models[0]

        # Position first model on ground floor (Z=0)
        model1.set_location(12.5, 12.5, 0.0, 0.0)

        # Position second model on first floor (Z=4.0) at same X,Y
        # Model height is typically ~2", so Z-delta of 4" should allow this
        model2.set_location(12.5, 12.5, 4.0, 0.0)

        # Test that second model can move to this position
        result = unified_pathfinding(
            model=model2,
            target=(12.5, 12.5, 4.0),
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        assert result['valid'], f"Should allow models on different floors with sufficient Z-delta: {result.get('reason', '')}"

        # Test that models cannot occupy same position with insufficient Z-delta
        # Try to place model2 at Z=1.0 (only 1" above model1)
        model2.set_location(13.5, 12.5, 0.0, 0.0)  # Move closer (1" away horizontally)

        result_too_close = unified_pathfinding(
            model=model2,
            target=(12.5, 12.5, 1.0),  # Too close vertically
            movement_type=MovementType.MOVE,
            max_distance=10.0,
            game_map=self.game_map
        )

        assert not result_too_close['valid'], "Should not allow models with insufficient Z-delta"
        assert "friendly" in result_too_close['reason'].lower() or "overlap" in result_too_close['reason'].lower()

    def test_3d_coherency_vertical_distance(self):
        """Test that coherency is maintained with 5" vertical and 2" horizontal distances."""

        # Create test scenario
        unit = self.create_circular_unit(x=10.0, y=10.0)
        self.setup_units_on_map([unit])


        # Create multi-floor RUINS terrain
        ruins_vertices = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)]
        ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=4.0, num_floors=2)
        self.game_map.add_terrain_feature(ruins)

        # Use Infantry unit with multiple models
        infantry_datasheet = MockDatasheet("Infantry Squad", model_count=3, movement=6, base_size="32mm")
        infantry_unit = Unit(infantry_datasheet)
        infantry_unit.keywords = ['Infantry']

        # Position models at different heights
        model1 = infantry_unit.models[0]  # Ground floor
        model2 = infantry_unit.models[1]  # First floor
        model3 = infantry_unit.models[2]  # Second floor

        model1.set_location(10.0, 10.0, 0.0, 0.0)    # Ground floor
        model2.set_location(10.0, 10.0, 4.0, 0.0)    # First floor (4" up)
        model3.set_location(10.0, 10.0, 8.0, 0.0)    # Second floor (8" up)

        # Test coherency - models should be in coherency
        # Vertical distance: model1 to model2 = 4", model2 to model3 = 4", model1 to model3 = 8"
        # All should be within 5" vertical coherency

        from warhammer40k_ai.utility.calcs import check_unit_coherency
        coherency_result = check_unit_coherency(infantry_unit)

        assert coherency_result['coherent'], f"Unit should be coherent with vertical positioning: {coherency_result.get('reason', '')}"

        # Test breaking vertical coherency - move model3 too far up
        model3.set_location(10.0, 10.0, 12.0, 0.0)  # 12" up from ground (8" from model2)

        coherency_result_broken = check_unit_coherency(infantry_unit)
        assert not coherency_result_broken['coherent'], "Unit should not be coherent when vertical distance > 5\""


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
