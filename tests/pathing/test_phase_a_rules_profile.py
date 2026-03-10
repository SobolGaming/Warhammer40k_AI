from __future__ import annotations

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import (
    MovementType,
    build_collision_trees,
    clear_collision_caches,
    get_validation_rules,
)
import warhammer40k_ai.utility.calcs as calcs


class MockDatasheet:
    def __init__(self, name: str, movement: int = 6, base_size: str = "32mm"):
        self.name = name
        self.faction_data = {"name": "MirrorFaction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, faction: str = "MirrorFaction", x: float = 0.0, y: float = 0.0) -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.faction = faction
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def test_phase_a_movement_profile_extracts_core_rules() -> None:
    unit = _make_unit("Walker", x=5.0, y=5.0)
    unit.keywords = ["VEHICLE"]
    unit.special_rules = {
        "move_over_low_terrain_height_value": 3.5,
        "move_over_low_terrain_height_types": ["move"],
        "move_over_friendly_monster_vehicle_types": ["move"],
    }
    unit.has_super_heavy_walker = lambda: True
    unit.has_flip_belt = lambda: True

    move_profile = build_movement_profile(unit, MovementType.MOVE)
    assert move_profile.free_climb_height_inches == 4.0
    assert move_profile.can_ignore_vertical_distance is True
    assert move_profile.can_breach_ruins_walls is False
    assert move_profile.can_end_on_upper_surfaces is False
    assert move_profile.pivot_cost_mode == "map_calculated"
    assert bool(move_profile.terrain_transition_rules["can_move_over_friendly_monster_vehicle"]) is True

    fall_back_profile = build_movement_profile(unit, MovementType.FALL_BACK)
    assert fall_back_profile.can_move_through_enemy_models is True
    assert bool(fall_back_profile.fall_back_interaction_rules["check_desperate_escape"]) is True


def test_phase_a_validation_rules_embed_movement_profile() -> None:
    unit = _make_unit("Infantry", x=8.0, y=8.0)
    profile = build_movement_profile(unit, MovementType.FALL_BACK)

    rules = get_validation_rules(
        MovementType.FALL_BACK,
        moving_unit=unit,
        movement_profile=profile,
    )

    assert rules["movement_profile"] is profile
    assert rules["can_move_through_enemy_models"] is True
    assert rules["free_climb_height_inches"] == profile.free_climb_height_inches
    assert rules["can_end_on_upper_surfaces"] == profile.can_end_on_upper_surfaces


def test_phase_a_build_collision_trees_uses_army_identity_not_faction() -> None:
    clear_collision_caches()

    game_map = Map(60, 44)

    moving = _make_unit("Moving", x=10.0, y=10.0)
    ally_same_faction_same_army = _make_unit("Ally", x=13.0, y=10.0)
    enemy_same_faction_other_army = _make_unit("EnemyMirror", x=16.0, y=10.0)

    army_a = Army("MirrorFaction", "Detachment A")
    army_b = Army("MirrorFaction", "Detachment B")
    moving.set_parent_army(army_a)
    ally_same_faction_same_army.set_parent_army(army_a)
    enemy_same_faction_other_army.set_parent_army(army_b)

    game_map.units = [moving, ally_same_faction_same_army, enemy_same_faction_other_army]

    trees = build_collision_trees(
        moving,
        MovementType.MOVE,
        game_map,
        moving_model=moving.models[0],
        max_distance=8.0,
    )

    enemy_tree = trees.get("enemy_models")
    friendly_tree = trees.get("friendly_models")

    enemy_count = len(enemy_tree.geometries) if enemy_tree is not None else 0
    friendly_count = len(friendly_tree.geometries) if friendly_tree is not None else 0

    assert enemy_count == 1
    assert friendly_count == 1

    expected_cache_key = (id(game_map), ("army", id(army_a)))
    assert expected_cache_key in calcs._enemy_model_cache
