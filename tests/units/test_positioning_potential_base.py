from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.units.unit_mixins.positioning_fight_movement_mixin import (
    PositioningFightMovementMixin,
)
from warhammer40k_ai.utility.model_base import Base, BaseType


class _PositioningHarness(PositioningFightMovementMixin):
    def __init__(self, base: Base) -> None:
        self.models = [SimpleNamespace(model_base=base)]


def test_create_potential_base_clones_base_without_mutating_source() -> None:
    source = Base(BaseType.HULL, (1.0, 2.0))
    source.set_position(4.0, 5.0, 0.5)
    source.set_facing(0.25)
    source.set_model_height(3.0)
    source.set_z_offset(0.75)
    source.set_compound_parts(
        (
            {
                "part_id": "sponson",
                "shape": "hull",
                "radius": (0.25, 0.5),
                "offset": (0.75, 0.0),
                "facing": 0.1,
            },
        )
    )
    harness = _PositioningHarness(source)

    candidate = harness._create_potential_base(8.0, 9.0, 1.25, 1.5)

    assert candidate is not source
    assert candidate.base_type is BaseType.HULL
    assert candidate.radius == pytest.approx((1.0, 2.0))
    assert candidate.model_height == pytest.approx(3.0)
    assert candidate.z_offset == pytest.approx(0.75)
    assert candidate.get_compound_parts() == source.get_compound_parts()
    assert (candidate.x, candidate.y, candidate.z) == pytest.approx((8.0, 9.0, 1.25))
    assert candidate.facing == pytest.approx(1.5)
    assert (source.x, source.y, source.z, source.facing) == pytest.approx((4.0, 5.0, 0.5, 0.25))
