from __future__ import annotations

from typing import Any, List, Tuple

from shapely.errors import GEOSException
from shapely.geometry import LineString, Polygon, box

from ..utility.constants import RUINS_FLOOR_HEIGHT, RUINS_FLOOR_THICKNESS, RUINS_WALL_THICKNESS


def create_preset_ruin_rect_12x6_variant1(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    long_wall_line = LineString([(2.25, 0.25), (9.75, 0.25)])
    short_wall_left_line_upper = LineString([(2.0 + half_t, 0.25), (2.0 + half_t, 3.75)])
    short_wall_right_line_upper = LineString([(10.0 - half_t, 0.25), (10.0 - half_t, 3.75)])
    short_wall_left_line_ground = short_wall_left_line_upper
    short_wall_right_line_ground = short_wall_right_line_upper
    long_wall_poly = long_wall_line.buffer(half_t)
    short_wall_left_poly_upper = short_wall_left_line_upper.buffer(half_t)
    short_wall_right_poly_upper = short_wall_right_line_upper.buffer(half_t)
    short_wall_left_poly_ground = short_wall_left_line_ground.buffer(half_t)
    short_wall_right_poly_ground = short_wall_right_line_ground.buffer(half_t)

    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    add_wall(long_wall_poly, floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(short_wall_left_poly_ground, floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(short_wall_right_poly_ground, floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(long_wall_poly, floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(short_wall_left_poly_upper, floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(short_wall_right_poly_upper, floor_level=1, height=RUINS_FLOOR_HEIGHT)

    z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
    z1_top = 2.25 + RUINS_FLOOR_HEIGHT
    for x_start, x_end in [(3.0, 5.0), (7.0, 9.0)]:
        openings.append(
            {
                "polygon": box(x_start, 0.25 - half_t, x_end, 0.25 + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            }
        )
    openings.append(
        {
            "polygon": box((2.0 + half_t) - half_t, 1.0, (2.0 + half_t) + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        }
    )
    openings.append(
        {
            "polygon": box((10.0 - half_t) - half_t, 1.0, (10.0 - half_t) + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        }
    )

    add_wall(long_wall_poly, floor_level=2, height=1.0)
    add_wall(short_wall_left_poly_upper, floor_level=2, height=1.0)
    add_wall(short_wall_right_poly_upper, floor_level=2, height=1.0)

    upper_floor_poly = box(2.0, 0.0, 10.0, 4.0)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": upper_floor_poly, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append(
        {"polygon": upper_floor_poly, "elevation": RUINS_FLOOR_HEIGHT * 2.0, "thickness": RUINS_FLOOR_THICKNESS}
    )
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_12x6_variant2(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    y_top_cl = 6.0 - half_t
    x_right_cl = 12.0 - half_t
    top_line_g = LineString([(4.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])
    top_line_l1 = LineString([(4.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])
    top_line_l2 = LineString([(6.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])
    right_line_g = LineString([(x_right_cl, 2.0 + half_t), (x_right_cl, 6.0 - half_t)])
    right_line_l1 = LineString([(x_right_cl, 3.0 + half_t), (x_right_cl, 6.0 - half_t)])
    right_line_l2 = LineString([(x_right_cl, 4.0 + half_t), (x_right_cl, 6.0 - half_t)])

    add_wall(top_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(right_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(right_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line_l2.buffer(half_t), floor_level=2, height=1.0)
    add_wall(right_line_l2.buffer(half_t), floor_level=2, height=1.0)

    z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
    z1_top = 2.25 + RUINS_FLOOR_HEIGHT
    for x_start, x_end in [(6.0, 8.0), (9.0, 11.0)]:
        openings.append(
            {
                "polygon": box(x_start, y_top_cl - half_t, x_end, y_top_cl + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            }
        )
    openings.append(
        {
            "polygon": box(x_right_cl - half_t, 3.5, x_right_cl + half_t, 5.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        }
    )

    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": Polygon([(12.0, 6.0), (4.0, 6.0), (12.0, 3.0)]), "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append(
        {
            "polygon": Polygon([(12.0, 6.0), (6.0, 6.0), (12.0, 4.0)]),
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        }
    )
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_12x6_variant3(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    y_top_cl = 6.0 - half_t
    x_left_cl = 0.0 + half_t
    top_line_g = LineString([(0.0 + half_t, y_top_cl), (8.0 - half_t, y_top_cl)])
    top_line_l1 = LineString([(0.0 + half_t, y_top_cl), (8.0 - half_t, y_top_cl)])
    top_line_l2 = LineString([(0.0 + half_t, y_top_cl), (6.0 - half_t, y_top_cl)])
    left_line_g = LineString([(x_left_cl, 2.0 + half_t), (x_left_cl, 6.0 - half_t)])
    left_line_l1 = LineString([(x_left_cl, 3.0 + half_t), (x_left_cl, 6.0 - half_t)])
    left_line_l2 = LineString([(x_left_cl, 4.0 + half_t), (x_left_cl, 6.0 - half_t)])

    add_wall(top_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(left_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(left_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line_l2.buffer(half_t), floor_level=2, height=1.0)
    add_wall(left_line_l2.buffer(half_t), floor_level=2, height=1.0)

    z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
    z1_top = 2.25 + RUINS_FLOOR_HEIGHT
    for x_start, x_end in [(1.0, 3.0), (4.0, 6.0)]:
        openings.append(
            {
                "polygon": box(x_start, y_top_cl - half_t, x_end, y_top_cl + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            }
        )
    openings.append(
        {
            "polygon": box(x_left_cl - half_t, 3.5, x_left_cl + half_t, 5.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        }
    )

    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": Polygon([(0.0, 6.0), (8.0, 6.0), (0.0, 3.0)]), "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append(
        {
            "polygon": Polygon([(0.0, 6.0), (6.0, 6.0), (0.0, 4.0)]),
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        }
    )
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_6x4_variant1(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.6, 0.6, 1.3, 1.4),
        box(2.0, 0.8, 2.6, 1.6),
        box(4.4, 0.7, 5.2, 1.3),
        box(1.0, 2.4, 1.8, 3.2),
        box(2.8, 2.2, 3.6, 3.0),
        box(4.2, 2.5, 5.4, 3.1),
    ]:
        add_rubble(rubble_piece)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_6x4_variant2(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    x_left_cl = 0.0 + half_t
    y_bottom_cl = 0.0 + half_t
    left_line = LineString([(x_left_cl, 0.0 + half_t), (x_left_cl, 4.0 - half_t)])
    bottom_line = LineString([(0.0 + half_t, y_bottom_cl), (6.0 - half_t, y_bottom_cl)])
    add_wall(left_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": footprint, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    add_wall(left_line.buffer(half_t), floor_level=1, height=1.0)
    add_wall(bottom_line.buffer(half_t), floor_level=1, height=1.0)
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_12x6_variant4(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.5, 0.6, 1.4, 1.5),
        box(2.0, 0.8, 3.5, 1.6),
        box(0.7, 2.2, 1.6, 3.1),
        box(2.3, 2.6, 3.7, 3.3),
        box(0.6, 4.2, 1.8, 5.0),
        box(2.2, 4.4, 3.6, 5.3),
    ]:
        add_rubble(rubble_piece)

    y2 = 2.0
    top_line = LineString([(4.0 + half_t, 6.0 - half_t), (12.0 - half_t, 6.0 - half_t)])
    right_line_4in = LineString([(12.0 - half_t, y2 + half_t), (12.0 - half_t, 6.0 - half_t)])
    add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(right_line_4in.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

    floor1_poly = box(4.0, 2.0, 12.0, 6.0)
    add_wall(LineString([(4.0 + half_t, 6.0 - half_t), (12.0 - half_t, 6.0 - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    add_wall(LineString([(12.0 - half_t, y2 + half_t), (12.0 - half_t, 6.0 - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": floor1_poly, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_12x6_variant5(ruins_cls: type) -> Any:
    from shapely.affinity import scale as _sh_scale

    variant4 = create_preset_ruin_rect_12x6_variant4(ruins_cls)

    def _mirror_geom(geometry: Any) -> Any:
        try:
            return _sh_scale(geometry, xfact=1.0, yfact=-1.0, origin=(0.0, 3.0))
        except (GEOSException, TypeError, ValueError):
            return geometry

    footprint = _mirror_geom(variant4.footprint)
    walls = [
        {
            "polygon": _mirror_geom(wall["polygon"]),
            "z_bottom": wall["z_bottom"],
            "z_top": wall["z_top"],
            "thickness": wall.get("thickness", 0.5),
        }
        for wall in variant4.walls
    ]
    openings = [
        {
            "polygon": _mirror_geom(opening["polygon"]),
            "z_bottom": opening["z_bottom"],
            "z_top": opening["z_top"],
            "allows_movement": opening.get("allows_movement", False),
            "allows_los": opening.get("allows_los", False),
        }
        for opening in variant4.openings
    ]
    floors = [
        {
            "polygon": _mirror_geom(floor["polygon"]),
            "elevation": floor["elevation"],
            "thickness": floor.get("thickness", 0.5),
        }
        for floor in variant4.floors
    ]
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_12x6_variant6(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.2, 0.6, 0.8, 1.4),
        box(1.0, 0.8, 1.8, 1.5),
        box(0.3, 2.4, 1.2, 3.2),
        box(1.1, 3.0, 1.9, 3.8),
        box(0.2, 4.6, 1.0, 5.4),
        box(1.1, 4.4, 1.9, 5.3),
        box(10.2, 0.6, 10.9, 1.3),
        box(11.1, 0.8, 11.8, 1.5),
        box(10.3, 2.3, 11.0, 3.1),
        box(11.1, 2.7, 11.8, 3.5),
        box(10.2, 4.5, 11.0, 5.3),
        box(11.1, 4.4, 11.8, 5.2),
    ]:
        add_rubble(rubble_piece)

    x_left = 2.0
    left_line = LineString([(x_left, 0.0 + half_t), (x_left, 5.0 - half_t)])
    bottom_line = LineString([(x_left + half_t, 0.0 + half_t), (9.0 - half_t, 0.0 + half_t)])
    add_wall(left_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(left_line.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(bottom_line.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
    add_wall(left_line.buffer(half_t), floor_level=2, height=1.0)
    add_wall(bottom_line.buffer(half_t), floor_level=2, height=1.0)

    z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
    z1_top = 2.25 + RUINS_FLOOR_HEIGHT
    for x0, x1 in [(3.0, 5.0), (6.0, 8.0)]:
        openings.append(
            {
                "polygon": box(x0, 0.0 + half_t - half_t, x1, 0.0 + half_t + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            }
        )
    openings.append(
        {
            "polygon": box(x_left - half_t, 1.5, x_left + half_t, 3.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        }
    )

    ruins_floor_tri = Polygon([(x_left, 0.0), (9.0, 0.0), (x_left, 5.0)])
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": ruins_floor_tri, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append(
        {"polygon": ruins_floor_tri, "elevation": RUINS_FLOOR_HEIGHT * 2.0, "thickness": RUINS_FLOOR_THICKNESS}
    )
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_10x5_variant1(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.4, 0.5, 1.1, 1.2),
        box(1.6, 0.6, 2.6, 1.3),
        box(0.6, 2.0, 1.4, 2.8),
        box(2.0, 2.2, 3.1, 3.0),
        box(0.5, 3.7, 1.5, 4.4),
        box(2.1, 3.6, 3.3, 4.3),
    ]:
        add_rubble(rubble_piece)

    x_join = 3.5
    y_top = 5.0
    join_line = LineString([(x_join, 0.0 + half_t), (x_join, y_top - half_t)])
    top_line = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)])
    add_wall(join_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    floor1_poly = box(x_join, 0.0, 10.0, y_top)
    add_wall(LineString([(x_join, 0.0 + half_t), (x_join, y_top - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    add_wall(LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": floor1_poly, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_10x5_variant2(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.4, 0.5, 1.1, 1.2),
        box(1.6, 0.6, 2.6, 1.3),
        box(0.6, 2.0, 1.4, 2.8),
        box(2.0, 2.2, 3.1, 3.0),
        box(0.5, 3.7, 1.5, 4.4),
        box(2.1, 3.6, 3.3, 4.3),
    ]:
        add_rubble(rubble_piece)

    x_join = 3.5
    y_top = 5.0
    right_line = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)])
    top_line = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)])
    add_wall(right_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    floor1_poly = box(x_join, 0.0, 10.0, y_top)
    add_wall(LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    add_wall(LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": floor1_poly, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


def create_preset_ruin_rect_10x5_variant3(ruins_cls: type) -> Any:
    footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])
    wall_thickness = RUINS_WALL_THICKNESS
    half_t = wall_thickness / 2.0
    walls: List[dict] = []
    openings: List[dict] = []
    floors: List[dict] = []

    def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
        walls.append(
            {
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            }
        )

    def add_rubble(poly: Polygon) -> None:
        walls.append({"polygon": poly, "z_bottom": 0.0, "z_top": 2.0, "thickness": wall_thickness})

    for rubble_piece in [
        box(0.4, 0.5, 1.1, 1.2),
        box(1.6, 0.6, 2.6, 1.3),
        box(0.6, 2.0, 1.4, 2.8),
        box(2.0, 2.2, 3.1, 3.0),
        box(0.5, 3.7, 1.5, 4.4),
        box(2.1, 3.6, 3.3, 4.3),
    ]:
        add_rubble(rubble_piece)

    x_join = 3.5
    y_top = 5.0
    right_line = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)])
    bottom_line = LineString([(x_join + half_t, 0.0 + half_t), (10.0 - half_t, 0.0 + half_t)])
    add_wall(right_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
    floor1_poly = box(x_join, 0.0, 10.0, y_top)
    add_wall(LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t), floor_level=1, height=1.0)
    add_wall(LineString([(x_join + half_t, 0.0 + half_t), (10.0 - half_t, 0.0 + half_t)]).buffer(half_t), floor_level=1, height=1.0)
    floors.append({"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS})
    floors.append({"polygon": floor1_poly, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS})
    return ruins_cls(footprint, walls=walls, openings=openings, floors=floors)


__all__ = [
    "create_preset_ruin_rect_10x5_variant1",
    "create_preset_ruin_rect_10x5_variant2",
    "create_preset_ruin_rect_10x5_variant3",
    "create_preset_ruin_rect_12x6_variant1",
    "create_preset_ruin_rect_12x6_variant2",
    "create_preset_ruin_rect_12x6_variant3",
    "create_preset_ruin_rect_12x6_variant4",
    "create_preset_ruin_rect_12x6_variant5",
    "create_preset_ruin_rect_12x6_variant6",
    "create_preset_ruin_rect_6x4_variant1",
    "create_preset_ruin_rect_6x4_variant2",
]
