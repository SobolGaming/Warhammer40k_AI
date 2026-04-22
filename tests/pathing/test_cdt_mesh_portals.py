import pytest
from shapely.geometry import Polygon

from warhammer40k_ai.pathing.cdt_mesh import _build_portals


def test_build_portals_connects_partial_shared_edges() -> None:
    upper = Polygon([(0.0, 0.0), (2.0, 0.0), (0.0, 1.0)])
    lower = Polygon([(0.5, 0.0), (1.0, -1.0), (1.5, 0.0)])

    portals = _build_portals("surface", (upper, lower))

    assert len(portals) == 1
    portal = portals[0]
    assert portal.triangle_a == 0
    assert portal.triangle_b == 1
    assert portal.length == pytest.approx(1.0)
    assert portal.midpoint_xy == pytest.approx((1.0, 0.0))
