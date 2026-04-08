from __future__ import annotations

from typing import Any

from shapely.errors import GEOSException
from shapely.geometry import Point

from ..utility.constants import RUINS_FLOOR_THICKNESS
from .terrain_runtime import TerrainType
from .terrain_visibility import build_reason_trace_entry


def _unit_root(unit: object | None) -> object | None:
    if unit is None:
        return None
    get_root = getattr(unit, "get_attached_unit_root", None)
    if callable(get_root):
        return get_root()
    return unit


def _unit_has_keyword(unit: object | None, keyword: str) -> bool:
    if unit is None:
        return False
    has_any_keyword = getattr(unit, "has_any_keyword", None)
    if not callable(has_any_keyword):
        return False
    try:
        return bool(has_any_keyword(keyword))
    except (TypeError, ValueError):
        return False


def _iter_root_models(root: object | None) -> list[object]:
    if root is None:
        return []
    get_models = getattr(root, "get_attached_unit_models", None)
    if callable(get_models):
        return list(get_models() or [])
    return list(getattr(root, "models", []) or [])


def _shape_covers(container: Any, target: Any) -> bool:
    if container is None or target is None:
        return False
    if hasattr(container, "covers"):
        return bool(container.covers(target))
    if hasattr(container, "contains"):
        return bool(container.contains(target))
    return False


def _candidate_base_for_pose(model: object | None, x: float, y: float, z: float) -> Any | None:
    if model is None:
        return None
    unit = getattr(model, "parent_unit", None)
    create_potential_base = getattr(unit, "_create_potential_base", None)
    model_base = getattr(model, "model_base", None)
    facing = float(getattr(model_base, "facing", 0.0) or 0.0)
    if callable(create_potential_base):
        try:
            candidate = create_potential_base(float(x), float(y), float(z), facing, model=model)
        except (AttributeError, TypeError, ValueError):
            candidate = None
        if candidate is not None:
            return candidate
    if model_base is None:
        return None
    try:
        from ..utility.model_base import clone_base

        candidate = clone_base(model_base)
        candidate.set_position(float(x), float(y), float(z))
        candidate.set_facing(float(facing))
        return candidate
    except (AttributeError, ImportError, TypeError, ValueError):
        return None


def _compound_part_surface_entry(source_model: object | None, *, part_id: str) -> dict[str, Any] | None:
    if source_model is None:
        return None
    model_base = getattr(source_model, "model_base", None)
    if model_base is None:
        return None
    get_parts = getattr(model_base, "get_compound_parts", None)
    parts = list(get_parts() or []) if callable(get_parts) else []
    if not parts:
        return None
    wanted = str(part_id or "").strip().lower()
    selected_part = None
    for part in parts:
        if str(part.get("part_id", "")).strip().lower() == wanted:
            selected_part = part
            break
    if selected_part is None:
        return None
    part_shape_at = getattr(model_base, "_compound_part_shape_at", None)
    if not callable(part_shape_at):
        return None
    try:
        shape = part_shape_at(
            selected_part,
            float(getattr(model_base, "x", 0.0) or 0.0),
            float(getattr(model_base, "y", 0.0) or 0.0),
            float(getattr(model_base, "facing", 0.0) or 0.0),
        )
    except (AttributeError, TypeError, ValueError, GEOSException):
        return None
    if shape is None:
        return None
    try:
        _bottom_z, top_z = model_base.volume_z_bounds()
    except (AttributeError, TypeError, ValueError):
        top_z = float(getattr(model_base, "z", 0.0) or 0.0) + float(getattr(model_base, "model_height", 0.0) or 0.0)
    return {
        "polygon": shape,
        "surface_z": float(top_z),
        "part_id": wanted,
    }


def _iter_emplacement_platform_surface_entries(
    game_map: object,
    *,
    moving_model: object | None = None,
    require_eligibility: bool = True,
) -> tuple[dict[str, Any], ...]:
    moving_unit = getattr(moving_model, "parent_unit", None) if moving_model is not None else None
    moving_army = None
    if moving_unit is not None:
        get_army = getattr(moving_unit, "get_parent_army", None)
        moving_army = get_army() if callable(get_army) else None
    if require_eligibility and moving_unit is not None and not _unit_has_keyword(moving_unit, "INFANTRY"):
        return tuple()

    entries: list[dict[str, Any]] = []
    seen_root_ids: set[str] = set()
    for unit in list(getattr(game_map, "units", []) or []):
        root = _unit_root(unit)
        if root is None:
            continue
        root_id = str(getattr(root, "id", "") or getattr(root, "_id", "") or f"object:{id(root)}")
        if root_id in seen_root_ids:
            continue
        seen_root_ids.add(root_id)
        if moving_army is not None:
            get_army = getattr(root, "get_parent_army", None)
            root_army = get_army() if callable(get_army) else None
            if root_army is not moving_army:
                continue
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not is_alive():
            continue
        if not bool(getattr(root, "deployed", True)):
            continue
        in_reserves = getattr(root, "is_in_reserves", None)
        if callable(in_reserves) and in_reserves():
            continue
        if bool(getattr(root, "is_embarked", False)):
            continue

        get_rule = getattr(root, "get_emplacement_platform_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if not isinstance(rule, dict):
            continue
        if moving_unit is not None:
            faction_keyword = str(rule.get("faction_keyword", "") or "").strip().upper()
            unit_keyword = str(rule.get("unit_keyword", "") or "").strip().upper()
            if faction_keyword and not _unit_has_keyword(moving_unit, faction_keyword):
                continue
            if require_eligibility and unit_keyword and not _unit_has_keyword(moving_unit, unit_keyword):
                continue
        models = _iter_root_models(root)
        if not models:
            continue
        surface = _compound_part_surface_entry(models[0], part_id=str(rule.get("part_id", "") or "platform"))
        if surface is None:
            continue
        entries.append(
            {
                "source_unit": root,
                "source_name": str(
                    rule.get("source", "") or getattr(root, "name", "Emplacement Platform") or "Emplacement Platform"
                ),
                "polygon": surface["polygon"],
                "surface_z": float(surface["surface_z"]),
                "part_id": str(surface["part_id"]),
                "surface_id": f"emplacement_platform:{root_id}",
            }
        )
    return tuple(entries)


def get_emplacement_platform_surface_entries(
    game_map: object,
    *,
    moving_model: object | None = None,
    require_eligibility: bool = True,
) -> tuple[dict[str, Any], ...]:
    return _iter_emplacement_platform_surface_entries(
        game_map,
        moving_model=moving_model,
        require_eligibility=require_eligibility,
    )


def get_emplacement_platform_placement(
    game_map: object,
    moving_model: object | None,
    *,
    x: float,
    y: float,
    z: float | None = None,
    require_eligibility: bool = True,
) -> dict[str, Any]:
    result = {
        "applies": False,
        "source_unit": None,
        "source_name": None,
        "surface_z": None,
        "reason": None,
    }
    candidate_base = _candidate_base_for_pose(moving_model, x=float(x), y=float(y), z=float(z or 0.0))
    if candidate_base is None:
        return result
    candidate_shape = candidate_base.get_base_shape()
    z_value = float(z) if z is not None else None
    for entry in _iter_emplacement_platform_surface_entries(
        game_map,
        moving_model=moving_model,
        require_eligibility=require_eligibility,
    ):
        polygon = entry.get("polygon")
        if not _shape_covers(polygon, candidate_shape):
            continue
        surface_z = float(entry.get("surface_z", 0.0) or 0.0)
        if z_value is not None and abs(surface_z - z_value) > 0.05:
            continue
        result["applies"] = True
        result["source_unit"] = entry.get("source_unit")
        result["source_name"] = entry.get("source_name")
        result["surface_z"] = surface_z
        result["reason"] = f"Supported by {entry.get('source_name') or 'Emplacement Platform'}"
        return result
    return result


def validate_model_surface_placement(
    game_map: object,
    model: object | None,
    position: tuple[float, float, float],
) -> dict[str, Any]:
    result: dict[str, Any] = {"valid": True, "reason": "Valid special-surface placement"}
    if model is None:
        return result
    x_pos, y_pos, z_pos = float(position[0]), float(position[1]), float(position[2])
    eligible = get_emplacement_platform_placement(
        game_map,
        model,
        x=x_pos,
        y=y_pos,
        z=z_pos,
        require_eligibility=True,
    )
    if eligible.get("applies", False):
        return result
    ineligible = get_emplacement_platform_placement(
        game_map,
        model,
        x=x_pos,
        y=y_pos,
        z=z_pos,
        require_eligibility=False,
    )
    if ineligible.get("applies", False):
        source_name = str(ineligible.get("source_name", "") or "Emplacement Platform").strip() or "Emplacement Platform"
        return {
            "valid": False,
            "reason": f"{source_name}: only friendly ASTRA MILITARUM INFANTRY models can be set up or end moves on the platform section.",
        }
    return result


def get_height_at_point(game_map: object, x: float, y: float) -> float:
    point = Point(float(x), float(y))
    max_height = 0.0
    for terrain_feature in list(getattr(game_map, "terrain_features", []) or []):
        footprint = getattr(terrain_feature, "footprint", None)
        if footprint is None or not footprint.contains(point):
            continue
        if getattr(terrain_feature, "terrain_type", None) == TerrainType.RUINS and hasattr(terrain_feature, "floors"):
            try:
                candidate_surfaces = []
                for floor in getattr(terrain_feature, "floors", []) or []:
                    floor_polygon = floor.get("polygon")
                    if floor_polygon is None or not floor_polygon.contains(point):
                        continue
                    elevation = float(floor.get("elevation", 0.0) or 0.0)
                    thickness = float(floor.get("thickness", RUINS_FLOOR_THICKNESS) or RUINS_FLOOR_THICKNESS)
                    candidate_surfaces.append(elevation + thickness)
                if candidate_surfaces:
                    max_height = max(max_height, min(candidate_surfaces))
                    continue
                max_height = max(max_height, float(RUINS_FLOOR_THICKNESS))
                continue
            except (TypeError, ValueError, KeyError, GEOSException):
                pass
        if hasattr(terrain_feature, "height"):
            max_height = max(max_height, float(getattr(terrain_feature, "height", 0.0) or 0.0))
        elif hasattr(terrain_feature, "rim_height"):
            max_height = max(max_height, float(getattr(terrain_feature, "rim_height", 0.0) or 0.0))
        else:
            max_height = max(max_height, 0.0)
    return max_height


def get_surface_options_for_model(game_map: object, model: object | None, x: float, y: float) -> list[float]:
    options = [float(get_height_at_point(game_map, x, y))]
    special = get_emplacement_platform_placement(
        game_map,
        model,
        x=float(x),
        y=float(y),
        require_eligibility=True,
    )
    if special.get("applies", False):
        options.append(float(special.get("surface_z", 0.0) or 0.0))
    unique: list[float] = []
    for value in options:
        if all(abs(float(value) - existing) > 1e-4 for existing in unique):
            unique.append(float(value))
    unique.sort()
    return unique


def get_surface_height_for_model(game_map: object, model: object | None, x: float, y: float) -> float:
    options = get_surface_options_for_model(game_map, model, x, y)
    if not options:
        return 0.0
    return float(max(options))


def _model_z(model: object | None) -> float:
    if model is None:
        return 0.0
    model_base = getattr(model, "model_base", None)
    if model_base is not None:
        try:
            return float(getattr(model_base, "z", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(getattr(model, "z", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _base_shape_at_current_pose(model: object | None):
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return None
    get_shape_at = getattr(model_base, "get_base_shape_at", None)
    if callable(get_shape_at):
        return get_shape_at(
            float(getattr(model_base, "x", 0.0) or 0.0),
            float(getattr(model_base, "y", 0.0) or 0.0),
            float(getattr(model_base, "facing", 0.0) or 0.0),
        )
    return model_base.get_base_shape()


def get_plunging_fire_context(game_map: object, attacker: object, target: object) -> dict[str, Any]:
    reason_trace: list[dict[str, Any]] = []
    result = {
        "applies": False,
        "legacy_height_qualifies": False,
        "attacker_on_qualifying_elevated_section": False,
        "target_contains_ground_level_models": False,
        "target_all_ground_level_models": False,
        "towering_short_range_exception_applies": False,
        "reason_trace": reason_trace,
    }

    attacker_z = _model_z(attacker)
    result["attacker_on_qualifying_elevated_section"] = attacker_z >= 3.0
    result["legacy_height_qualifies"] = attacker_z >= 6.0

    alive_targets = [model for model in list(getattr(target, "models", []) or []) if bool(getattr(model, "is_alive", True))]
    if alive_targets:
        ground_level_flags = [abs(_model_z(model)) < 1.0 for model in alive_targets]
        result["target_contains_ground_level_models"] = any(ground_level_flags)
        result["target_all_ground_level_models"] = all(ground_level_flags)
    else:
        result["target_contains_ground_level_models"] = False
        result["target_all_ground_level_models"] = False

    attacker_shape = _base_shape_at_current_pose(attacker)
    attacker_wholly_within_ruins = False
    if attacker_shape is not None:
        for terrain in list(getattr(game_map, "terrain_features", []) or []):
            if getattr(terrain, "terrain_type", None) != TerrainType.RUINS:
                continue
            footprint = getattr(terrain, "footprint", None)
            if footprint is None:
                continue
            if hasattr(footprint, "covers") and footprint.covers(attacker_shape):
                attacker_wholly_within_ruins = True
                break
            if hasattr(footprint, "contains") and footprint.contains(attacker_shape):
                attacker_wholly_within_ruins = True
                break

    target_root = _unit_root(target)
    attacker_root = _unit_root(getattr(attacker, "parent_unit", None))
    attacker_is_towering = bool(getattr(attacker_root, "is_towering", False))
    target_is_towering = bool(getattr(target_root, "is_towering", False))
    if attacker_shape is not None and alive_targets:
        target_model = alive_targets[0]
        target_base = getattr(target_model, "model_base", None)
        attacker_base = getattr(attacker, "model_base", None)
        if attacker_base is not None and target_base is not None:
            try:
                dx = float(getattr(target_base, "x", 0.0) or 0.0) - float(getattr(attacker_base, "x", 0.0) or 0.0)
                dy = float(getattr(target_base, "y", 0.0) or 0.0) - float(getattr(attacker_base, "y", 0.0) or 0.0)
                distance = (dx * dx + dy * dy) ** 0.5
            except (TypeError, ValueError):
                distance = 0.0
            result["towering_short_range_exception_applies"] = bool((attacker_is_towering or target_is_towering) and distance <= 12.0)

    if result["attacker_on_qualifying_elevated_section"]:
        reason_trace.append(
            build_reason_trace_entry(
                "ATTACKER_ON_QUALIFYING_ELEVATED_SECTION",
                "Attacker is on a terrain section at least 3\" above ground level.",
                metadata={"attacker_z": attacker_z},
            )
        )
    else:
        reason_trace.append(
            build_reason_trace_entry(
                "ATTACKER_NOT_ELEVATED_ENOUGH",
                "Attacker is not on a qualifying elevated section for preview plunging queries.",
                metadata={"attacker_z": attacker_z},
            )
        )

    if result["target_contains_ground_level_models"]:
        reason_trace.append(
            build_reason_trace_entry("TARGET_HAS_GROUND_MODELS", "Target unit contains one or more ground-level models.")
        )
    if result["towering_short_range_exception_applies"]:
        reason_trace.append(
            build_reason_trace_entry(
                "TOWERING_SHORT_RANGE_EXCEPTION_QUERY",
                "Preview towering short-range plunging query is satisfied.",
            )
        )

    result["applies"] = bool(
        result["legacy_height_qualifies"] and result["target_all_ground_level_models"] and attacker_wholly_within_ruins
    )
    if result["applies"]:
        reason_trace.append(
            build_reason_trace_entry(
                "LEGACY_PLUNGING_FIRE_APPLIES",
                "Legacy plunging fire AP modifier applies under the current compatibility rules.",
            )
        )
    else:
        reason_trace.append(
            build_reason_trace_entry(
                "LEGACY_PLUNGING_FIRE_DOES_NOT_APPLY",
                "Legacy plunging fire AP modifier does not apply under the current compatibility rules.",
                metadata={
                    "legacy_height_qualifies": result["legacy_height_qualifies"],
                    "target_all_ground_level_models": result["target_all_ground_level_models"],
                    "attacker_wholly_within_ruins": attacker_wholly_within_ruins,
                },
            )
        )
    return result


__all__ = [
    "get_emplacement_platform_placement",
    "get_emplacement_platform_surface_entries",
    "get_height_at_point",
    "get_plunging_fire_context",
    "get_surface_height_for_model",
    "get_surface_options_for_model",
    "validate_model_surface_placement",
]
