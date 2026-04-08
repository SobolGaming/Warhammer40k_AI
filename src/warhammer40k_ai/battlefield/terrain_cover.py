from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from shapely.errors import GEOSException
from shapely.ops import unary_union

from .terrain_runtime import TerrainType
from .terrain_visibility import build_reason_trace_entry, is_fully_visible_due_to_terrain


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


def _footprint_and_bounding_box_for_models(models: list[object]) -> tuple[Any, dict[str, tuple[float, float, float]] | None]:
    shapes = []
    max_z = 0.0
    for model in list(models or []):
        if model is None or not bool(getattr(model, "is_alive", True)):
            continue
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        shape = base.get_base_shape()
        if shape is None:
            continue
        shapes.append(shape)
        try:
            z_here = float(getattr(base, "z", 0.0) or 0.0)
        except (TypeError, ValueError):
            z_here = 0.0
        try:
            height = float(getattr(base, "model_height", 0.0) or 0.0)
        except (TypeError, ValueError):
            height = 0.0
        max_z = max(max_z, z_here + height)
    if not shapes:
        return None, None
    try:
        footprint = unary_union(shapes)
    except GEOSException:
        footprint = shapes[0]
    try:
        bounds = footprint.bounds
    except (TypeError, ValueError):
        return None, None
    return footprint, {
        "min": (float(bounds[0]), float(bounds[1]), 0.0),
        "max": (float(bounds[2]), float(bounds[3]), float(max_z)),
    }


def _weapon_ignores_cover(weapon_profile: Any | None) -> bool:
    if weapon_profile is None:
        return False
    parent_wargear = getattr(weapon_profile, "parent_wargear", None)
    ignores_cover = getattr(parent_wargear, "is_ignores_cover", None)
    if not callable(ignores_cover):
        return False
    return bool(ignores_cover())


def _cover_result_template() -> dict[str, Any]:
    return {
        "has_benefit_of_cover": False,
        "source_terrain_type": None,
        "reason": None,
        "reason_trace": [],
        "attacker_skill_modifiers": [],
        "save_modifiers": [],
        "compatibility_mode": "SAVE_BONUS_COMPATIBILITY",
    }


def get_benefit_of_cover_for_ranged_attack(
    game_map: object,
    attacking_unit: object,
    target_model: object,
    weapon_profile: Any | None = None,
    ap: int | None = None,
) -> dict[str, Any]:
    """Compatibility adapter for current terrain-based Benefit of Cover."""
    del ap
    result = _cover_result_template()
    if _weapon_ignores_cover(weapon_profile):
        result["reason_trace"].append(
            build_reason_trace_entry("IGNORES_COVER", "Weapon ignores terrain cover modifiers.")
        )
        return result

    for terrain in list(getattr(game_map, "terrain_features", []) or []):
        terrain_type = getattr(terrain, "terrain_type", None)
        if terrain_type not in (TerrainType.RUINS, TerrainType.WOODS):
            continue
        footprint = getattr(terrain, "footprint", None)
        if footprint is None:
            continue

        base_shape = getattr(getattr(target_model, "model_base", None), "get_base_shape", lambda: None)()
        if base_shape is not None and footprint.covers(base_shape):
            result["has_benefit_of_cover"] = True
            result["source_terrain_type"] = getattr(terrain_type, "name", str(terrain_type))
            result["reason"] = "Target model wholly within terrain feature"
            result["reason_trace"].append(
                build_reason_trace_entry(
                    "TARGET_WHOLLY_WITHIN_TERRAIN",
                    "Target model is wholly within the terrain feature footprint.",
                    metadata={"terrain_id": str(getattr(terrain, "id", "") or "")},
                )
            )
            result["save_modifiers"].append(
                {
                    "kind": "BENEFIT_OF_COVER",
                    "mode": "SAVE_BONUS_COMPATIBILITY",
                    "value": 1,
                    "source": result["source_terrain_type"],
                }
            )
            return result

        for attacker_model in list(getattr(attacking_unit, "models", []) or []):
            if attacker_model is None or not bool(getattr(attacker_model, "is_alive", False)):
                continue
            if is_fully_visible_due_to_terrain(attacker_model, target_model, terrain):
                continue
            result["has_benefit_of_cover"] = True
            result["source_terrain_type"] = getattr(terrain_type, "name", str(terrain_type))
            result["reason"] = (
                f"Not fully visible to {getattr(attacker_model, 'name', 'an attacker model')} due to terrain"
            )
            result["reason_trace"].append(
                build_reason_trace_entry(
                    "TERRAIN_BREAKS_FULL_VISIBILITY",
                    "Target is not fully visible to every attacking model because of terrain.",
                    metadata={
                        "terrain_id": str(getattr(terrain, "id", "") or ""),
                        "attacker_model_name": str(getattr(attacker_model, "name", "") or ""),
                    },
                )
            )
            result["save_modifiers"].append(
                {
                    "kind": "BENEFIT_OF_COVER",
                    "mode": "SAVE_BONUS_COMPATIBILITY",
                    "value": 1,
                    "source": result["source_terrain_type"],
                }
            )
            return result

    result["reason_trace"].append(
        build_reason_trace_entry("NO_TERRAIN_COVER", "No terrain feature granted Benefit of Cover.")
    )
    return result


def get_benefit_of_cover_from_fortifications(
    game_map: object,
    attacking_unit: object,
    target_model: object,
    fortification_units: list[object],
    weapon_profile: Any | None = None,
) -> dict[str, Any]:
    result = {
        "has_benefit_of_cover": False,
        "source_unit": None,
        "reason": None,
        "reason_trace": [],
        "attacker_skill_modifiers": [],
        "save_modifiers": [],
        "compatibility_mode": "SAVE_BONUS_COMPATIBILITY",
    }
    if target_model is None or attacking_unit is None:
        result["reason_trace"].append(
            build_reason_trace_entry("MISSING_COMBATANTS", "Target model or attacking unit is missing.")
        )
        return result
    if _weapon_ignores_cover(weapon_profile):
        result["reason_trace"].append(
            build_reason_trace_entry("IGNORES_COVER", "Weapon ignores fortification cover modifiers.")
        )
        return result
    if not fortification_units:
        result["reason_trace"].append(
            build_reason_trace_entry("NO_FORTIFICATIONS", "No fortification units were available for cover evaluation.")
        )
        return result

    target_root = _unit_root(getattr(target_model, "parent_unit", None))
    for fortification in list(fortification_units or []):
        root = _unit_root(fortification)
        if root is None or root is target_root:
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

        get_rule = getattr(root, "get_fortification_cover_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if not rule:
            continue

        get_models = getattr(root, "get_attached_unit_models", None)
        root_models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        footprint, bounding_box = _footprint_and_bounding_box_for_models(root_models)
        if footprint is None or bounding_box is None:
            continue
        proxy = SimpleNamespace(footprint=footprint, bounding_box=bounding_box)
        for attacker_model in list(getattr(attacking_unit, "models", []) or []):
            if attacker_model is None or not bool(getattr(attacker_model, "is_alive", False)):
                continue
            if is_fully_visible_due_to_terrain(attacker_model, target_model, proxy):
                continue
            result["has_benefit_of_cover"] = True
            result["source_unit"] = root
            source_name = str(rule.get("source", "") or getattr(root, "name", "Fortification") or "Fortification")
            result["reason"] = f"Not fully visible due to {source_name}"
            result["reason_trace"].append(
                build_reason_trace_entry(
                    "FORTIFICATION_BREAKS_FULL_VISIBILITY",
                    "Target is not fully visible because of a fortification cover source.",
                    metadata={"source_unit_id": str(getattr(root, "id", "") or ""), "source": source_name},
                )
            )
            result["save_modifiers"].append(
                {
                    "kind": "BENEFIT_OF_COVER",
                    "mode": "SAVE_BONUS_COMPATIBILITY",
                    "value": 1,
                    "source": source_name,
                }
            )
            return result

    result["reason_trace"].append(
        build_reason_trace_entry("NO_FORTIFICATION_COVER", "No fortification cover source granted Benefit of Cover.")
    )
    return result


def get_selfless_protector_bonus_for_ranged_attack(
    game_map: object,
    attacking_unit: object,
    target_model: object,
    protector_units: list[object],
    weapon_profile: Any | None = None,
) -> dict[str, Any]:
    result = {
        "applies": False,
        "source_unit": None,
        "source_model": None,
        "grants_benefit_of_cover": False,
        "invulnerable_save": None,
        "reason": None,
        "reason_trace": [],
        "attacker_skill_modifiers": [],
        "save_modifiers": [],
        "compatibility_mode": "SAVE_BONUS_COMPATIBILITY",
    }
    if target_model is None or attacking_unit is None or not protector_units:
        return result

    target_root = _unit_root(getattr(target_model, "parent_unit", None))
    if target_root is None:
        return result

    ignores_cover = _weapon_ignores_cover(weapon_profile)
    for protector in list(protector_units or []):
        protector_root = _unit_root(protector)
        if protector_root is None or protector_root is target_root:
            continue
        is_alive = getattr(protector_root, "is_alive", None)
        if callable(is_alive) and not is_alive():
            continue
        if not bool(getattr(protector_root, "deployed", True)):
            continue
        in_reserves = getattr(protector_root, "is_in_reserves", None)
        if callable(in_reserves) and in_reserves():
            continue
        if bool(getattr(protector_root, "is_embarked", False)):
            continue

        get_rule = getattr(protector_root, "get_selfless_protector_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if not isinstance(rule, dict):
            continue
        target_keyword = str(rule.get("target_keyword", "") or "").strip().upper()
        if target_keyword:
            model_has_any = getattr(target_model, "has_any_keyword", None)
            target_matches = False
            if callable(model_has_any):
                try:
                    target_matches = bool(model_has_any(target_keyword))
                except (TypeError, ValueError):
                    target_matches = False
            if not target_matches:
                model_has_keyword = getattr(target_model, "has_keyword", None)
                if callable(model_has_keyword):
                    try:
                        target_matches = bool(model_has_keyword(target_keyword))
                    except (TypeError, ValueError):
                        target_matches = False
            if not target_matches and not _unit_has_keyword(target_root, target_keyword):
                continue

        get_models = getattr(protector_root, "get_attached_unit_models", None)
        protector_models = list(get_models() or []) if callable(get_models) else list(getattr(protector_root, "models", []) or [])
        if not protector_models:
            continue

        source_model = None
        source_model_id = str(rule.get("model_id", "") or "")
        if source_model_id:
            for model in protector_models:
                if model is None:
                    continue
                if str(getattr(model, "id", "") or getattr(model, "_id", "") or "") != source_model_id:
                    continue
                source_model = model
                break
        if source_model is None:
            for model in protector_models:
                if model is None or not bool(getattr(model, "is_alive", True)):
                    continue
                source_model = model
                break
        if source_model is None:
            continue

        footprint, bounding_box = _footprint_and_bounding_box_for_models([source_model])
        if footprint is None or bounding_box is None:
            continue
        proxy = SimpleNamespace(footprint=footprint, bounding_box=bounding_box)
        for attacker_model in list(getattr(attacking_unit, "models", []) or []):
            if attacker_model is None or not bool(getattr(attacker_model, "is_alive", False)):
                continue
            if is_fully_visible_due_to_terrain(attacker_model, target_model, proxy):
                continue
            result["applies"] = True
            result["source_unit"] = protector_root
            result["source_model"] = source_model
            try:
                invulnerable_save = int(rule.get("invulnerable_save", 0) or 0)
            except (TypeError, ValueError):
                invulnerable_save = 0
            result["invulnerable_save"] = int(invulnerable_save) if invulnerable_save > 0 else None
            if not ignores_cover:
                result["grants_benefit_of_cover"] = True
                result["save_modifiers"].append(
                    {
                        "kind": "BENEFIT_OF_COVER",
                        "mode": "SAVE_BONUS_COMPATIBILITY",
                        "value": 1,
                        "source": str(rule.get("source", "") or getattr(protector_root, "name", "Selfless Protector")),
                    }
                )
            source_name = str(
                rule.get("source", "") or getattr(protector_root, "name", "Selfless Protector") or "Selfless Protector"
            )
            result["reason"] = f"Not fully visible due to {source_name}"
            result["reason_trace"].append(
                build_reason_trace_entry(
                    "SELFLESS_PROTECTOR_APPLIES",
                    "A selfless protector model breaks full visibility to the target.",
                    metadata={"source_unit_id": str(getattr(protector_root, "id", "") or ""), "source": source_name},
                )
            )
            return result
    return result


def get_defence_line_bonus_for_ranged_attack(
    game_map: object,
    attacking_unit: object,
    target_model: object,
    fortification_units: list[object],
    weapon_profile: Any | None = None,
) -> dict[str, Any]:
    result = {
        "applies": False,
        "source_unit": None,
        "invulnerable_save": None,
        "reason": None,
        "reason_trace": [],
    }
    if target_model is None or attacking_unit is None:
        return result
    if _weapon_ignores_cover(weapon_profile):
        result["reason_trace"].append(
            build_reason_trace_entry("IGNORES_COVER", "Weapon ignores defence-line cover style bonuses.")
        )
        return result

    target_unit = getattr(target_model, "parent_unit", None)
    target_root = _unit_root(target_unit)
    for fortification in list(fortification_units or []):
        root = _unit_root(fortification)
        if root is None or root is target_root:
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

        get_rule = getattr(root, "get_defence_line_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if not isinstance(rule, dict):
            continue
        faction_keyword = str(rule.get("faction_keyword", "") or "").strip().upper()
        unit_keyword = str(rule.get("unit_keyword", "") or "").strip().upper()
        if faction_keyword and not _unit_has_keyword(target_unit, faction_keyword):
            continue
        if unit_keyword and not _unit_has_keyword(target_unit, unit_keyword):
            continue

        get_cover_rule = getattr(root, "get_fortification_cover_rule", None)
        cover_rule = get_cover_rule() if callable(get_cover_rule) else None
        if not isinstance(cover_rule, dict):
            continue

        get_models = getattr(root, "get_attached_unit_models", None)
        root_models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        footprint, bounding_box = _footprint_and_bounding_box_for_models(root_models)
        if footprint is None or bounding_box is None:
            continue
        proxy = SimpleNamespace(footprint=footprint, bounding_box=bounding_box)
        for attacker_model in list(getattr(attacking_unit, "models", []) or []):
            if attacker_model is None or not bool(getattr(attacker_model, "is_alive", False)):
                continue
            if is_fully_visible_due_to_terrain(attacker_model, target_model, proxy):
                continue
            result["applies"] = True
            result["source_unit"] = root
            result["invulnerable_save"] = int(rule.get("invulnerable_save", 0) or 0)
            source_name = str(rule.get("source", "") or getattr(root, "name", "Defence Line") or "Defence Line")
            result["reason"] = f"Not fully visible due to {source_name}"
            result["reason_trace"].append(
                build_reason_trace_entry(
                    "DEFENCE_LINE_APPLIES",
                    "A defence line breaks full visibility to the target.",
                    metadata={"source_unit_id": str(getattr(root, "id", "") or ""), "source": source_name},
                )
            )
            return result
    return result


__all__ = [
    "get_benefit_of_cover_for_ranged_attack",
    "get_benefit_of_cover_from_fortifications",
    "get_defence_line_bonus_for_ranged_attack",
    "get_selfless_protector_bonus_for_ranged_attack",
]
