from __future__ import annotations

from shapely.geometry import Polygon


def create_boundary_polygon(width: float, height: float) -> Polygon:
    return Polygon(
        [
            (0.0, 0.0),
            (float(width), 0.0),
            (float(width), float(height)),
            (0.0, float(height)),
        ]
    )


def battlefield_edge_repulsors(
    width: float,
    height: float,
    *,
    repulsor_thickness: float = 0.5,
) -> list[Polygon]:
    thickness = float(repulsor_thickness)
    board_width = float(width)
    board_height = float(height)
    return [
        Polygon(
            [
                (-thickness, -thickness),
                (0.0, -thickness),
                (0.0, board_height + thickness),
                (-thickness, board_height + thickness),
            ]
        ),
        Polygon(
            [
                (board_width, -thickness),
                (board_width + thickness, -thickness),
                (board_width + thickness, board_height + thickness),
                (board_width, board_height + thickness),
            ]
        ),
        Polygon(
            [
                (-thickness, -thickness),
                (board_width + thickness, -thickness),
                (board_width + thickness, 0.0),
                (-thickness, 0.0),
            ]
        ),
        Polygon(
            [
                (-thickness, board_height),
                (board_width + thickness, board_height),
                (board_width + thickness, board_height + thickness),
                (-thickness, board_height + thickness),
            ]
        ),
    ]


__all__ = ["battlefield_edge_repulsors", "create_boundary_polygon"]
