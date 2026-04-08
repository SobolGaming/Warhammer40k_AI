from __future__ import annotations

from typing import Optional, Tuple

from shapely.errors import GEOSException

from ..units.model import Model
from ..units.unit import Unit
from ..utility.calcs import _resolve_ruins_floor_level
from ..utility.constants import RUINS_FLOOR_THICKNESS
from .terrain_runtime import TerrainFeature, TerrainType


def _unit_collision_models(unit: Unit) -> list[Model]:
    getter = getattr(unit, "get_models_for_collision", None)
    if callable(getter):
        return list(getter() or [])
    return list(getattr(unit, "models", []) or [])


def validate_ruins_placement(
    unit: Unit,
    position: Tuple[float, float, float],
    terrain_features: list[TerrainFeature],
    moving_model: Optional[Model] = None,
) -> dict:
    x, y, z = position
    for terrain in terrain_features:
        if terrain.terrain_type != TerrainType.RUINS:
            continue

        if moving_model is not None:
            try:
                test_base = moving_model.model_base.get_base_shape_at(
                    x,
                    y,
                    getattr(moving_model.model_base, "facing", 0.0),
                )
            except (AttributeError, TypeError, ValueError, GEOSException):
                test_base = None
            if test_base is None or not test_base.intersects(terrain.footprint):
                continue
        else:
            any_intersection = False
            for model in list(getattr(unit, "models", []) or []):
                model_pos = model.get_location()
                if not model_pos:
                    continue
                mx = model_pos[0]
                my = model_pos[1]
                try:
                    model_base = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, "facing", 0.0))
                except (AttributeError, TypeError, ValueError, GEOSException):
                    model_base = None
                if model_base is not None and model_base.intersects(terrain.footprint):
                    any_intersection = True
                    break
            if not any_intersection:
                continue

        floors = getattr(terrain, "floors", []) or []
        floor_level, current_floor = _resolve_ruins_floor_level(z, terrain)
        if current_floor is None or floor_level is None:
            return {"valid": False, "reason": f'Position not on a valid floor level (z={z:.1f})', "floor_level": 0}

        def _base_overlaps_wall(model: Model, mx: float, my: float, mz: float) -> str | None:
            try:
                base_geom = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, "facing", 0.0))
            except (AttributeError, TypeError, ValueError, GEOSException):
                return "Failed to get model base geometry for wall check"
            for wall in getattr(terrain, "walls", []) or []:
                if wall.get("z_bottom", 0.0) <= mz <= wall.get("z_top", 0.0):
                    try:
                        if base_geom.intersects(wall.get("polygon")):
                            return "Model base overlaps a RUINS wall"
                    except (TypeError, ValueError, GEOSException):
                        return "Error during wall intersection check"
            return None

        def _vertical_clearance_issue(model: Model, base_geom, floor_ref: dict) -> str | None:
            if base_geom is None:
                return None
            current_elev = float(floor_ref.get("elevation", 0.0) or 0.0)
            current_top = current_elev + float(
                floor_ref.get("thickness", RUINS_FLOOR_THICKNESS) or RUINS_FLOOR_THICKNESS
            )
            nearest_upper_floor = None
            min_elev = float("inf")
            for floor in floors:
                elev = float(floor.get("elevation", 0.0) or 0.0)
                if elev <= current_elev:
                    continue
                floor_poly = floor.get("polygon")
                if floor_poly is None:
                    continue
                try:
                    overlaps_xy = base_geom.intersects(floor_poly)
                except (TypeError, ValueError, GEOSException):
                    overlaps_xy = False
                if not overlaps_xy:
                    continue
                if elev < min_elev:
                    min_elev = elev
                    nearest_upper_floor = floor
            if nearest_upper_floor is None:
                return None
            next_bottom = float(nearest_upper_floor.get("elevation", 0.0) or 0.0)
            vertical_gap = max(0.0, next_bottom - current_top)
            safety_buffer = 0.10
            model_height = getattr(model.model_base, "model_height", 2.0)
            if model_height >= max(0.0, vertical_gap - safety_buffer):
                return (
                    f'Model height {model_height:.2f}" exceeds available vertical gap '
                    f'{vertical_gap:.2f}" under next floor'
                )
            return None

        if floor_level == 0:
            if moving_model is not None:
                wall_reason = _base_overlaps_wall(moving_model, x, y, z)
                if wall_reason:
                    return {"valid": False, "reason": wall_reason, "floor_level": floor_level}
                try:
                    base_geom = moving_model.model_base.get_base_shape_at(
                        x,
                        y,
                        getattr(moving_model.model_base, "facing", 0.0),
                    )
                except (AttributeError, TypeError, ValueError, GEOSException):
                    base_geom = None
                if base_geom is not None:
                    clearance_issue = _vertical_clearance_issue(moving_model, base_geom, current_floor)
                    if clearance_issue:
                        return {"valid": False, "reason": clearance_issue, "floor_level": floor_level}
            else:
                for model in _unit_collision_models(unit):
                    model_pos = model.get_location()
                    if not model_pos:
                        continue
                    mx = model_pos[0]
                    my = model_pos[1]
                    mz = model_pos[2] if len(model_pos) > 2 else 0.0
                    wall_reason = _base_overlaps_wall(model, mx, my, mz)
                    if wall_reason:
                        return {"valid": False, "reason": wall_reason, "floor_level": floor_level}
                    try:
                        base_geom = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, "facing", 0.0))
                    except (AttributeError, TypeError, ValueError, GEOSException):
                        base_geom = None
                    if base_geom is not None:
                        clearance_issue = _vertical_clearance_issue(model, base_geom, current_floor)
                        if clearance_issue:
                            return {"valid": False, "reason": clearance_issue, "floor_level": floor_level}
            return {"valid": True, "reason": "Valid ground floor placement", "floor_level": floor_level}

        if not unit.can_access_upper_floors():
            return {
                "valid": False,
                "reason": f"Unit type cannot access upper floors (floor level {floor_level})",
                "floor_level": floor_level,
            }

        floor_poly = current_floor.get("polygon")
        if floor_level > 0 and floor_poly:
            if moving_model is not None:
                base_geom = moving_model.model_base.get_base_shape_at(
                    x,
                    y,
                    getattr(moving_model.model_base, "facing", 0.0),
                )
                try:
                    floor_covers_base = floor_poly.covers(base_geom) if hasattr(floor_poly, "covers") else floor_poly.contains(base_geom)
                except (TypeError, ValueError, GEOSException):
                    floor_covers_base = False
                if not floor_covers_base:
                    return {
                        "valid": False,
                        "reason": f"Model base would overhang floor on level {floor_level}",
                        "floor_level": floor_level,
                    }
                clearance_issue = _vertical_clearance_issue(moving_model, base_geom, current_floor)
                if clearance_issue:
                    return {"valid": False, "reason": clearance_issue, "floor_level": floor_level}
            else:
                for model in _unit_collision_models(unit):
                    model_pos = model.get_location()
                    if not model_pos:
                        continue
                    mx = model_pos[0]
                    my = model_pos[1]
                    base_geom = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, "facing", 0.0))
                    try:
                        floor_covers_base = floor_poly.covers(base_geom) if hasattr(floor_poly, "covers") else floor_poly.contains(base_geom)
                    except (TypeError, ValueError, GEOSException):
                        floor_covers_base = False
                    if not floor_covers_base:
                        return {
                            "valid": False,
                            "reason": f"Model base would overhang floor on level {floor_level}",
                            "floor_level": floor_level,
                        }
                    clearance_issue = _vertical_clearance_issue(model, base_geom, current_floor)
                    if clearance_issue:
                        return {"valid": False, "reason": clearance_issue, "floor_level": floor_level}

        if floor_level > 0:
            if moving_model is not None:
                wall_reason = _base_overlaps_wall(moving_model, x, y, z)
                if wall_reason:
                    return {"valid": False, "reason": wall_reason, "floor_level": floor_level}
            else:
                for model in _unit_collision_models(unit):
                    model_pos = model.get_location()
                    if not model_pos:
                        continue
                    mx = model_pos[0]
                    my = model_pos[1]
                    mz = model_pos[2] if len(model_pos) > 2 else z
                    wall_reason = _base_overlaps_wall(model, mx, my, mz)
                    if wall_reason:
                        return {"valid": False, "reason": wall_reason, "floor_level": floor_level}

        return {"valid": True, "reason": f"Valid upper floor placement (level {floor_level})", "floor_level": floor_level}

    return {"valid": True, "reason": "No RUINS terrain at position", "floor_level": 0}


__all__ = ["validate_ruins_placement"]
