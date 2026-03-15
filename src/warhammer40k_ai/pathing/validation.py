from __future__ import annotations

"""Temporary compatibility bridge for movement validation internals.

The authoritative planner API lives in ``pathing.api``. This module is a narrow
adapter while legacy validation/collision internals are still hosted in
``utility.calcs``. Keep all imports here function-local to avoid import cycles.
"""

from typing import Mapping, Optional


def get_validation_rules(
    movement_type: object,
    target_unit: object = None,
    *,
    moving_unit: object = None,
    target_units: Optional[tuple[object, ...]] = None,
    movement_profile: object = None,
) -> dict[str, object]:
    from ..utility.calcs import get_validation_rules as _get_validation_rules

    return dict(
        _get_validation_rules(
            movement_type,
            target_unit,
            moving_unit=moving_unit,
            target_units=target_units,
            movement_profile=movement_profile,
        )
    )


def build_collision_trees(
    moving_unit: object,
    movement_type: object,
    game_map: object,
    *,
    moving_model: object = None,
    moved_models_in_unit: Optional[set[object]] = None,
    max_distance: Optional[float] = None,
    target_position: Optional[tuple[float, float, float]] = None,
    movement_profile: object = None,
) -> dict[str, object]:
    from ..utility.calcs import build_collision_trees as _build_collision_trees

    return _build_collision_trees(
        moving_unit,
        movement_type,
        game_map,
        moving_model=moving_model,
        moved_models_in_unit=moved_models_in_unit,
        max_distance=max_distance,
        target_position=target_position,
        movement_profile=movement_profile,
    )


def is_position_valid_unified_detailed(
    position: tuple[float, float, float],
    model: object,
    collision_trees: Mapping[str, object],
    validation_rules: Mapping[str, object],
    game_map: object = None,
    *,
    is_final_position: bool = True,
) -> dict[str, object]:
    from ..utility.calcs import is_position_valid_unified_detailed as _is_position_valid_unified_detailed

    return dict(
        _is_position_valid_unified_detailed(
            position,
            model,
            dict(collision_trees),
            dict(validation_rules),
            game_map,
            is_final_position=is_final_position,
        )
    )


def get_pivot_cost(unit: object) -> float:
    from ..utility.calcs import get_pivot_cost as _get_pivot_cost

    return float(_get_pivot_cost(unit))


__all__ = [
    "build_collision_trees",
    "get_pivot_cost",
    "get_validation_rules",
    "is_position_valid_unified_detailed",
]
