#!/usr/bin/env python3
"""
Example demonstrating the new RUINS terrain system with walls, floors, and windows.
"""

from src.warhammer40k_ai.classes.map import (
    Map, Obstacle, ObstacleType, 
    RuinsComponent, RuinsComponentType, Window
)
from src.warhammer40k_ai.classes.unit import Unit
from src.warhammer40k_ai.classes.model import Model
from src.warhammer40k_ai.utility.model_base import Base, BaseType

def create_simple_ruins_building():
    """Create a simple 2-story ruins building with walls and floors."""
    
    # Define building footprint (10" x 8" building)
    building_footprint = [
        (10.0, 10.0),  # Bottom-left corner
        (20.0, 10.0),  # Bottom-right corner
        (20.0, 18.0),  # Top-right corner
        (10.0, 18.0)   # Top-left corner
    ]
    
    # Create ruins using the helper method
    ruins = Obstacle.create_ruins(
        building_footprint=building_footprint,
        wall_height=4.0,      # 4" tall walls per floor
        num_floors=1,         # Ground floor + 1st floor
        has_windows=True      # Include windows for line of sight
    )
    
    return ruins

def create_custom_ruins_building():
    """Create a custom ruins building with specific wall and floor configurations."""
    
    # Building footprint
    building_footprint = [
        (30.0, 30.0),
        (40.0, 30.0),
        (40.0, 40.0),
        (30.0, 40.0)
    ]
    
    components = []
    
    # Ground floor
    ground_floor = RuinsComponent(
        vertices=building_footprint,
        component_type=RuinsComponentType.FLOOR,
        height=0.5,  # Floor thickness
        floor_level=0
    )
    components.append(ground_floor)
    
    # First floor
    first_floor = RuinsComponent(
        vertices=building_footprint,
        component_type=RuinsComponentType.FLOOR,
        height=0.5,
        floor_level=1
    )
    components.append(first_floor)
    
    # Create walls with custom windows
    wall_segments = [
        # South wall (with large window)
        [(30.0, 30.0), (40.0, 30.0)],
        # East wall (no windows)
        [(40.0, 30.0), (40.0, 40.0)],
        # North wall (with small window)
        [(40.0, 40.0), (30.0, 40.0)],
        # West wall (with door opening)
        [(30.0, 40.0), (30.0, 30.0)]
    ]
    
    for i, wall_vertices in enumerate(wall_segments):
        windows = []
        
        if i == 0:  # South wall - large window
            windows.append(Window(
                start_position=0.2,
                end_position=0.8,
                height_bottom=1.0,
                height_top=3.5
            ))
        elif i == 2:  # North wall - small window
            windows.append(Window(
                start_position=0.4,
                end_position=0.6,
                height_bottom=2.0,
                height_top=3.0
            ))
        elif i == 3:  # West wall - door opening (ground floor only)
            windows.append(Window(
                start_position=0.3,
                end_position=0.7,
                height_bottom=0.0,  # Door goes to ground
                height_top=3.0
            ))
        
        # Ground floor walls
        ground_wall = RuinsComponent(
            vertices=wall_vertices,
            component_type=RuinsComponentType.WALL,
            height=4.0,
            floor_level=0,
            windows=windows if i != 3 else [windows[0]]  # Door only on ground floor
        )
        components.append(ground_wall)
        
        # First floor walls (no door opening)
        first_floor_windows = windows if i != 3 else []  # No door on first floor
        first_wall = RuinsComponent(
            vertices=wall_vertices,
            component_type=RuinsComponentType.WALL,
            height=4.0,
            floor_level=1,
            windows=first_floor_windows
        )
        components.append(first_wall)
    
    # Create the ruins obstacle
    ruins = Obstacle(
        vertices=building_footprint,
        terrain_type=ObstacleType.RUINS,
        height=8.0,  # Total height (2 floors * 4")
        ruins_components=components
    )
    
    return ruins

def demonstrate_ruins_traversal():
    """Demonstrate how different unit types interact with ruins."""
    
    # Create a map
    game_map = Map(width=48, height=72)
    
    # Add ruins buildings
    simple_ruins = create_simple_ruins_building()
    custom_ruins = create_custom_ruins_building()
    
    game_map.add_obstacle(simple_ruins)
    game_map.add_obstacle(custom_ruins)
    
    # Create test units
    from tests.mocks import MockDatasheet
    
    # Infantry unit (can move through walls)
    infantry_datasheet = MockDatasheet("Space Marines", movement=6, base_size="32mm")
    infantry_unit = Unit(infantry_datasheet)
    infantry_unit.keywords = ['Infantry']
    
    # Vehicle unit (cannot move through walls)
    vehicle_datasheet = MockDatasheet("Rhino", movement=12, base_size="120x92mm")
    vehicle_unit = Unit(vehicle_datasheet)
    vehicle_unit.keywords = ['Vehicle']
    
    print("=== RUINS Terrain System Demonstration ===\n")
    
    print("Simple Ruins Building:")
    print(f"  - Footprint: 10\"x8\"")
    print(f"  - Floors: {simple_ruins.get_max_floor_level() + 1}")
    print(f"  - Total walls: {len(simple_ruins.get_walls())}")
    print(f"  - Total floors: {len(simple_ruins.get_floors())}")
    
    print(f"\nCustom Ruins Building:")
    print(f"  - Footprint: 10\"x10\"")
    print(f"  - Floors: {custom_ruins.get_max_floor_level() + 1}")
    print(f"  - Total walls: {len(custom_ruins.get_walls())}")
    print(f"  - Total floors: {len(custom_ruins.get_floors())}")
    
    # Check wall traversal
    print(f"\nWall Traversal Rules:")
    for ruins in [simple_ruins, custom_ruins]:
        walls = ruins.get_walls()
        if walls:
            sample_wall = walls[0]
            infantry_can_traverse = ruins.can_unit_traverse_wall(infantry_unit, sample_wall)
            vehicle_can_traverse = ruins.can_unit_traverse_wall(vehicle_unit, sample_wall)
            
            print(f"  Infantry can traverse walls: {infantry_can_traverse}")
            print(f"  Vehicle can traverse walls: {vehicle_can_traverse}")
            break
    
    # Show floor heights
    print(f"\nFloor Heights:")
    for floor_level in range(custom_ruins.get_max_floor_level() + 1):
        height = custom_ruins.get_floor_height(floor_level)
        floor_name = "Ground" if floor_level == 0 else f"Floor {floor_level}"
        print(f"  {floor_name}: {height}\" above ground")
    
    # Show windows
    print(f"\nWindows in Custom Ruins:")
    for i, wall in enumerate(custom_ruins.get_walls()):
        if wall.windows:
            for j, window in enumerate(wall.windows):
                print(f"  Wall {i//2 + 1}, Floor {wall.floor_level + 1}: Window from {window.start_position:.1%} to {window.end_position:.1%} of wall")
                print(f"    Height: {window.height_bottom}\" to {window.height_top}\" above floor")

if __name__ == "__main__":
    demonstrate_ruins_traversal()
