import pytest
from typing import List

from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.battlefield.terrain_visibility import (
    TerrainVisibilityRecord,
    VisibilityFrameContext,
    get_visibility_frame_context,
)
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.utility.model_base import Base, BaseType


class MockDatasheet:
    def __init__(self, name: str, movement=6, model_count=1, base_size="32mm"):
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


def create_unit(
    name: str,
    x: float,
    y: float,
    z: float = 0.0,
    faction: str = "A",
    base: Base = None,
    model_count: int = 1,
) -> Unit:
    ds = MockDatasheet(name, model_count=model_count)
    unit = Unit(ds)
    if base is not None:
        unit.models[0].model_base = base
    for index, model in enumerate(unit.models):
        model.set_location(x + index * 1.5, y, z, 0.0)
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_armies(game_map: Map, units_a: List[Unit], units_b: List[Unit]):
    army_a = Army.with_detachment("Army A", "Detachment A")
    army_b = Army.with_detachment("Army B", "Detachment B")
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = units_a + units_b
    return army_a, army_b


class TestLineOfSight:
    def setup_method(self):
        self.map = Map(width=48, height=72)

    def test_clear_los_no_obstacles(self):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 20.0, 10.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_los_cache_reuses_identical_model_pair_geometry(self):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 20.0, 10.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)
        context = get_visibility_frame_context(self.map)
        first_cache_size = len(context.los_cache)
        assert first_cache_size == 1

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)
        assert get_visibility_frame_context(self.map) is context
        assert len(context.los_cache) == first_cache_size

        target.models[0].set_location(21.0, 10.0, 0.0, 0.0)
        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)
        moved_context = get_visibility_frame_context(self.map)
        assert moved_context is not context
        assert len(moved_context.los_cache) == 1

    def test_enemy_model_blocks_los(self):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 30.0, 10.0, faction="B")
        blocker = create_unit("Enemy Blocker", 20.0, 10.0, faction="B")
        attach_to_armies(self.map, [shooter], [target, blocker])

        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_friendly_does_not_block_los(self):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 30.0, 10.0, faction="B")
        friend = create_unit("Friend", 20.0, 10.0)  # Same faction as shooter
        attach_to_armies(self.map, [shooter, friend], [target])

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_ruins_block_outside_to_outside(self):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 30.0, 10.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        # Ruins footprint between shooter (10,10) and target (30,10)
        ruins = TerrainFactory.create_ruins([(15.0, 8.0), (25.0, 8.0), (25.0, 12.0), (15.0, 12.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_ruins_allow_los_into_via_opening(self):
        shooter = create_unit("Shooter", 20.0, 6.0)
        # Target inside the ruins area
        target = create_unit("Target", 20.0, 10.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        # Ruins with a door on the bottom edge centered at (20,8)
        ruins = TerrainFactory.create_ruins([(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        # Shooter below, target inside; line should pass through the ground-level door opening
        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_ruins_block_outside_to_outside_even_with_opening(self):
        shooter = create_unit("Shooter", 13.0, 9.0)
        target = create_unit("Target", 27.0, 9.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        # Door aligned between shooter/target; outside-to-outside should still be blocked.
        ruins = TerrainFactory.create_ruins([(15.0, 8.0), (25.0, 8.0), (25.0, 12.0), (15.0, 12.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_aircraft_uses_normal_los_not_ruins_block(self):
        # Place shooter and target outside on opposite sides with ray skimming through bottom door
        shooter = create_unit("Shooter", 14.0, 8.0)
        shooter.keywords = ["Aircraft"]  # Aircraft exception
        target = create_unit("Target", 26.0, 8.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        # Ruins between them; door exists on bottom edge at center
        ruins = TerrainFactory.create_ruins([(15.0, 8.0), (25.0, 8.0), (25.0, 12.0), (15.0, 12.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        # For Aircraft, special ruins blanket block is skipped; with a bottom-edge door aligned,
        # normal wall checks allow LOS through the opening.
        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_ruins_block_outside_to_inside_without_opening(self):
        shooter = create_unit("Shooter", 20.0, 6.0)
        target = create_unit("Target", 20.0, 12.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins(
            [(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)],
            wall_height=4.0,
            num_floors=1,
            has_windows=False,
            has_doors=False,
        )
        self.map.add_terrain_feature(ruins)

        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_partially_inside_non_towering_cannot_see_out(self):
        # Place shooter so its base overlaps the southern wall buffer (partially inside)
        shooter_base = Base(BaseType.CIRCULAR, 1.0)
        shooter = create_unit("Shooter", 16.0, 7.5, base=shooter_base)  # Slightly below the bottom edge
        # Target outside the ruins footprint (below)
        target = create_unit("Target", 20.0, 6.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins([(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        # Move shooter slightly up so the base intersects the footprint but is not wholly covered
        shooter.models[0].set_location(16.9, 8.1, 0.0, 0.0)  # Overlapping edge -> partially inside

        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_wholly_within_can_see_out_via_opening(self):
        shooter = create_unit("Shooter", 20.0, 12.0)
        target = create_unit("Target", 20.0, 6.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins([(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        # Place shooter wholly within the footprint
        shooter.models[0].set_location(20.0, 12.0, 0.0, 0.0)

        # LOS should pass out through the ground-level door opening
        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_wholly_within_cannot_see_out_without_opening(self):
        shooter = create_unit("Shooter", 20.0, 12.0)
        target = create_unit("Target", 20.0, 6.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins(
            [(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)],
            wall_height=4.0,
            num_floors=1,
            has_windows=False,
            has_doors=False,
        )
        self.map.add_terrain_feature(ruins)

        shooter.models[0].set_location(20.0, 12.0, 0.0, 0.0)
        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_towering_inside_can_see_out_via_opening(self):
        shooter = create_unit("Shooter", 20.0, 12.0)
        shooter.keywords = ["Towering"]
        target = create_unit("Target", 20.0, 6.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins([(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)], wall_height=4.0, num_floors=1)
        self.map.add_terrain_feature(ruins)

        shooter.models[0].set_location(20.0, 12.0, 0.0, 0.0)

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_towering_within_cannot_see_out_without_opening(self):
        shooter = create_unit("Shooter", 20.0, 12.0)
        shooter.keywords = ["Towering"]
        target = create_unit("Target", 20.0, 6.0, faction="B")
        attach_to_armies(self.map, [shooter], [target])

        ruins = TerrainFactory.create_ruins(
            [(16.0, 8.0), (24.0, 8.0), (24.0, 16.0), (16.0, 16.0)],
            wall_height=4.0,
            num_floors=1,
            has_windows=False,
            has_doors=False,
        )
        self.map.add_terrain_feature(ruins)

        shooter.models[0].set_location(20.0, 12.0, 0.0, 0.0)
        assert not shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)

    def test_unit_los_stops_after_first_visible_target_model(self, monkeypatch):
        shooter = create_unit("Shooter", 10.0, 10.0)
        target = create_unit("Target", 20.0, 10.0, faction="B", model_count=2)
        target.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        target.models[1].set_location(35.0, 10.0, 0.0, 0.0)
        attach_to_armies(self.map, [shooter], [target])

        seen_target_ids = []
        original = VisibilityFrameContext.can_model_see_model

        def counting_can_model_see_model(self, shooter_model, target_model, **kwargs):
            seen_target_ids.append(target_model.id)
            return original(self, shooter_model, target_model, **kwargs)

        monkeypatch.setattr(VisibilityFrameContext, "can_model_see_model", counting_can_model_see_model)

        assert shooter._has_line_of_sight_to_target(shooter.models[0], target, self.map)
        assert seen_target_ids == [target.models[0].id]

    def test_segment_blocking_stops_after_first_confirmed_blocker(self, monkeypatch):
        class BlockingFootprint:
            bounds = (0.0, 0.0, 10.0, 10.0)

            def intersects(self, _line):
                return True

        class UnexpectedFootprint:
            bounds = (0.0, 0.0, 10.0, 10.0)

            def intersects(self, _line):
                raise AssertionError("segment blocker search should stop after the first blocker")

        context = get_visibility_frame_context(self.map)
        context.terrain_records = (
            TerrainVisibilityRecord(
                stable_id="first",
                terrain=object(),
                footprint=BlockingFootprint(),
                bounds=(0.0, 0.0, 10.0, 10.0),
                z_bounds=(0.0, 10.0),
                is_ruins=True,
                has_walls=True,
            ),
            TerrainVisibilityRecord(
                stable_id="second",
                terrain=object(),
                footprint=UnexpectedFootprint(),
                bounds=(0.0, 0.0, 10.0, 10.0),
                z_bounds=(0.0, 10.0),
                is_ruins=True,
                has_walls=True,
            ),
        )
        def fake_line_candidates(self, _tree, records, _line2d, _p0, _p1):
            return list(records) if records is self.terrain_records else []

        monkeypatch.setattr(VisibilityFrameContext, "_line_candidates", fake_line_candidates)

        blocked, blocker_id = context.segment_is_blocked(
            (0.0, 5.0, 1.0),
            (10.0, 5.0, 1.0),
            shooter_unit_id="shooter",
            target_unit_ids=("target",),
            enemy_unit_ids=("target",),
            shooter_is_aircraft=False,
            target_is_aircraft=False,
            shooter_is_towering=False,
            shooter_ruins_states=(("first", False, False), ("second", False, False)),
            target_ruins_states=(("first", False), ("second", False)),
            ruleset_signature=(False, "", ()),
        )

        assert blocked is True
        assert blocker_id == "first"
