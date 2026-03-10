from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import LineString

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.utility.calcs import (
    check_desperate_escape_requirements,
    get_enemy_models_moved_over,
    get_enemy_units_moved_over,
)
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, movement: int = 12, base_size: str = "32mm"):
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


def _make_unit(name: str, *, x: float, y: float, z: float = 0.0) -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.models[0].set_location(x, y, z, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def _assign_armies(*units: Unit) -> None:
    armies = [SimpleNamespace(name=f"Army{index}") for index, _ in enumerate(units, start=1)]
    for unit, army in zip(units, armies):
        unit.set_parent_army(army)


def test_phase_f_swept_move_over_detects_centerline_miss() -> None:
    game_map = Map(24, 24)
    mover = _make_unit("Mover", x=2.0, y=10.0)
    enemy = _make_unit("Enemy", x=10.0, y=11.8)
    _assign_armies(mover, enemy)
    game_map.units = [mover, enemy]

    path = [(2.0, 10.0, 0.0), (18.0, 10.0, 0.0)]
    centerline = LineString([(path[0][0], path[0][1]), (path[1][0], path[1][1])])
    assert not centerline.intersects(enemy.models[0].model_base.get_base_shape())

    moved_units = get_enemy_units_moved_over(mover.models[0], path, game_map, require_vertical_overlap=True)
    moved_models = get_enemy_models_moved_over(mover.models[0], path, game_map, require_vertical_overlap=True)

    assert moved_units
    assert moved_models
    assert moved_units[0] is enemy
    assert moved_models[0] is enemy.models[0]


def test_phase_f_swept_move_over_respects_vertical_overlap_gate() -> None:
    game_map = Map(24, 24)
    mover = _make_unit("Mover", x=2.0, y=10.0, z=5.0)
    enemy = _make_unit("Enemy", x=10.0, y=10.0, z=0.0)
    _assign_armies(mover, enemy)
    game_map.units = [mover, enemy]

    path = [(2.0, 10.0, 5.0), (18.0, 10.0, 5.0)]
    gated = get_enemy_units_moved_over(mover.models[0], path, game_map, require_vertical_overlap=True)
    ungated = get_enemy_units_moved_over(mover.models[0], path, game_map, require_vertical_overlap=False)

    assert gated == []
    assert ungated == [enemy]


def test_phase_f_desperate_escape_uses_swept_overlap_detection() -> None:
    game_map = Map(24, 24)
    mover = _make_unit("Mover", x=2.0, y=10.0)
    enemy = _make_unit("Enemy", x=10.0, y=11.8)
    _assign_armies(mover, enemy)
    game_map.units = [mover, enemy]

    path = [(2.0, 10.0, 0.0), (18.0, 10.0, 0.0)]
    result = check_desperate_escape_requirements(
        mover.models[0],
        path,
        {"check_desperate_escape": True},
        game_map,
    )

    assert result["required"] is True
    assert result["path_through_enemy"] is True
    assert "path goes through enemy models" in str(result["reason"]).lower()
