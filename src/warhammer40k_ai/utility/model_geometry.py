from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from shapely.ops import unary_union

from .calcs import convert_mm_to_inches
from .model_base import BaseType, create_ellipse, create_rectangle

logger = logging.getLogger(__name__)

_DEFAULT_OVERRIDES_FILE = ("data", "model_geometry_overrides.json")
_SHAPE_TYPES = {"circle", "ellipse", "hull"}
_ENTRY_TYPES = {"hull", "compound"}
_GUIDE_CLASSIFICATIONS = {"hull", "unique", "circle", "ellipse"}

_HEIGHT_INFANTRY_OR_CHARACTER = 1.4
_HEIGHT_BEAST_OR_CAVALRY = 1.1
_HEIGHT_MONSTER_OR_WALKER = 1.55
_HEIGHT_VEHICLE = 0.8
_HEIGHT_AIRCRAFT = 0.6
_FLYING_BASE_Z_OFFSET_BY_MINOR_MM: tuple[tuple[float, float], ...] = (
    (35.0, 20.0),
    (65.0, 32.0),
    (100.0, 45.0),
    (120.0, 55.0),
    (math.inf, 65.0),
)
_AUTO_FLYING_HULL_SCALE_BY_MINOR_MM: tuple[tuple[float, tuple[float, float]], ...] = (
    (35.0, (1.8, 1.5)),
    (65.0, (3.0, 2.25)),
    (100.0, (2.3, 1.85)),
    (120.0, (2.1, 1.75)),
    (math.inf, (1.9, 1.6)),
)
_AUTO_FLYING_PROXY_MIN_SUPPORT_BASE_MM = 0.0


@dataclass(frozen=True)
class ResolvedModelGeometry:
    base_type: BaseType
    radius: tuple[float, float]
    model_height: float
    z_offset: float
    compound_parts: tuple[dict, ...]
    geometry_source: str
    height_source: str


def normalize_geometry_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _default_overrides_path() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root.joinpath(*_DEFAULT_OVERRIDES_FILE)


def _to_inch(value_mm: object, *, field: str, context: str) -> float:
    value = float(value_mm)
    if value <= 0.0:
        raise ValueError(f"{context}: '{field}' must be > 0, got {value!r}")
    return float(convert_mm_to_inches(value))


def _to_non_negative_inch(value_mm: object, *, field: str, context: str) -> float:
    value = float(value_mm)
    if value < 0.0:
        raise ValueError(f"{context}: '{field}' must be >= 0, got {value!r}")
    return float(convert_mm_to_inches(value))


def _validate_shape_spec(shape_spec: dict, *, context: str) -> None:
    shape = str(shape_spec.get("shape", "")).strip().lower()
    if shape not in _SHAPE_TYPES:
        raise ValueError(f"{context}: unsupported shape '{shape}'")
    if shape == "circle":
        _to_inch(shape_spec.get("diameter_mm"), field="diameter_mm", context=context)
    elif shape == "ellipse":
        _to_inch(shape_spec.get("major_mm"), field="major_mm", context=context)
        _to_inch(shape_spec.get("minor_mm"), field="minor_mm", context=context)
    else:
        _to_inch(shape_spec.get("length_mm"), field="length_mm", context=context)
        _to_inch(shape_spec.get("width_mm"), field="width_mm", context=context)


def _validate_unit_entry(unit_key: str, entry: dict) -> None:
    context = f"model_geometry_overrides.units.{unit_key}"
    if not isinstance(entry, dict):
        raise ValueError(f"{context} must be an object")

    entry_type = str(entry.get("type", "")).strip().lower()
    shape = str(entry.get("shape", "")).strip().lower()

    if entry_type in _ENTRY_TYPES:
        if entry_type == "hull":
            _to_inch(entry.get("length_mm"), field="length_mm", context=context)
            _to_inch(entry.get("width_mm"), field="width_mm", context=context)
        elif entry_type == "compound":
            parts = entry.get("parts")
            if not isinstance(parts, list) or not parts:
                raise ValueError(f"{context}.parts must be a non-empty array")
            per_part_heights = []
            for idx, part in enumerate(parts):
                if not isinstance(part, dict):
                    raise ValueError(f"{context}.parts[{idx}] must be an object")
                _validate_shape_spec(part, context=f"{context}.parts[{idx}]")
                if "height_mm" in part:
                    _to_inch(part.get("height_mm"), field="height_mm", context=f"{context}.parts[{idx}]")
                    per_part_heights.append(True)
                else:
                    per_part_heights.append(False)
                if "offset_mm" in part:
                    offset = part.get("offset_mm")
                    if not isinstance(offset, list) or len(offset) != 2:
                        raise ValueError(f"{context}.parts[{idx}].offset_mm must be [x_mm, y_mm]")
                    float(offset[0])
                    float(offset[1])
            if "height_mm" not in entry and not all(per_part_heights):
                raise ValueError(
                    f"{context} must define 'height_mm' or provide 'height_mm' for every part"
                )
    elif shape:
        _validate_shape_spec(entry, context=context)
    else:
        raise ValueError(f"{context} must define type in {_ENTRY_TYPES} or a supported shape")

    if "height_mm" in entry:
        _to_inch(entry.get("height_mm"), field="height_mm", context=context)
    if "z_offset_mm" in entry:
        _to_non_negative_inch(entry.get("z_offset_mm"), field="z_offset_mm", context=context)


def _validate_catalog(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("model geometry overrides JSON must be an object")
    units = data.get("units")
    if not isinstance(units, dict):
        raise ValueError("model geometry overrides JSON must contain object 'units'")
    for unit_key, entry in units.items():
        _validate_unit_entry(str(unit_key), entry)

    aliases = data.get("aliases", {})
    if aliases and not isinstance(aliases, dict):
        raise ValueError("model geometry overrides 'aliases' must be an object")
    for alias_key, unit_key in aliases.items():
        if str(unit_key) not in units:
            raise ValueError(
                f"model geometry alias '{alias_key}' references unknown unit '{unit_key}'"
            )

    base_size_guide = data.get("base_size_guide", {})
    if base_size_guide and not isinstance(base_size_guide, dict):
        raise ValueError("model geometry overrides 'base_size_guide' must be an object")
    guide_units = base_size_guide.get("units", {})
    if guide_units and not isinstance(guide_units, dict):
        raise ValueError("model geometry overrides 'base_size_guide.units' must be an object")
    for guide_key, guide_entry in guide_units.items():
        if not isinstance(guide_entry, dict):
            raise ValueError(f"base_size_guide.units.{guide_key} must be an object")
        classification = str(guide_entry.get("classification", "")).strip().lower()
        if classification not in _GUIDE_CLASSIFICATIONS:
            raise ValueError(
                f"base_size_guide.units.{guide_key}.classification must be one of {_GUIDE_CLASSIFICATIONS}"
            )
        if "requires_manual_geometry" in guide_entry:
            bool(guide_entry.get("requires_manual_geometry"))
        geometry_key = str(guide_entry.get("geometry_key", "")).strip()
        if geometry_key and geometry_key not in units:
            raise ValueError(
                f"base_size_guide.units.{guide_key}.geometry_key references unknown unit '{geometry_key}'"
            )


@lru_cache(maxsize=1)
def load_model_geometry_catalog(path: Optional[str] = None) -> dict:
    resolved_path = Path(path) if path else _default_overrides_path()
    if not resolved_path.exists():
        return {"schema_version": "", "units": {}, "aliases": {}, "base_size_guide": {"units": {}}}
    raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    _validate_catalog(raw)
    return raw


def _lookup_unit_key(
    *,
    catalog: dict,
    datasheet_id: Optional[str],
    datasheet_name: str,
    model_name: str,
    preferred_key: Optional[str] = None,
) -> Optional[str]:
    units: dict = catalog.get("units", {})
    aliases: dict = catalog.get("aliases", {})

    normalized_units = {normalize_geometry_key(k): k for k in units}
    normalized_aliases = {normalize_geometry_key(k): v for k, v in aliases.items()}

    candidates: list[str] = []
    if preferred_key:
        candidates.append(str(preferred_key))
    if datasheet_id:
        candidates.append(str(datasheet_id))
    if datasheet_name:
        candidates.append(str(datasheet_name))
    if model_name:
        candidates.append(str(model_name))
    if datasheet_name and model_name:
        candidates.append(f"{datasheet_name}::{model_name}")
        candidates.append(f"{normalize_geometry_key(datasheet_name)}::{normalize_geometry_key(model_name)}")

    for candidate in candidates:
        if candidate in units:
            return candidate
        if candidate in aliases:
            return str(aliases[candidate])
        normalized = normalize_geometry_key(candidate)
        if normalized in normalized_units:
            return normalized_units[normalized]
        if normalized in normalized_aliases:
            return str(normalized_aliases[normalized])
    return None


def _lookup_base_size_guide_entry(
    *,
    catalog: dict,
    datasheet_id: Optional[str],
    datasheet_name: str,
    model_name: str,
) -> dict:
    guide_units: dict = (catalog.get("base_size_guide", {}) or {}).get("units", {}) or {}
    normalized_guide = {normalize_geometry_key(k): v for k, v in guide_units.items()}

    candidates: list[str] = []
    if datasheet_id:
        candidates.append(str(datasheet_id))
    if datasheet_name:
        candidates.append(str(datasheet_name))
    if model_name:
        candidates.append(str(model_name))
    if datasheet_name and model_name:
        candidates.append(f"{datasheet_name}::{model_name}")
        candidates.append(f"{normalize_geometry_key(datasheet_name)}::{normalize_geometry_key(model_name)}")

    for candidate in candidates:
        if candidate in guide_units:
            return dict(guide_units[candidate] or {})
        normalized = normalize_geometry_key(candidate)
        if normalized in normalized_guide:
            return dict(normalized_guide[normalized] or {})
    return {}


def _shape_to_radius(shape: str, spec: dict, *, context: str) -> tuple[float, float]:
    shape = shape.lower()
    if shape == "circle":
        diameter = _to_inch(spec.get("diameter_mm"), field="diameter_mm", context=context)
        r = diameter / 2.0
        return (r, r)
    if shape == "ellipse":
        major = _to_inch(spec.get("major_mm"), field="major_mm", context=context)
        minor = _to_inch(spec.get("minor_mm"), field="minor_mm", context=context)
        return (major / 2.0, minor / 2.0)
    if shape == "hull":
        length = _to_inch(spec.get("length_mm"), field="length_mm", context=context)
        width = _to_inch(spec.get("width_mm"), field="width_mm", context=context)
        return (length / 2.0, width / 2.0)
    raise ValueError(f"{context}: unsupported shape '{shape}'")


def _part_to_local_spec(part: dict, *, context: str) -> dict:
    shape = str(part.get("shape", "")).strip().lower()
    radius = _shape_to_radius(shape, part, context=context)
    if "offset_mm" in part:
        offset_mm = part.get("offset_mm")
        if not isinstance(offset_mm, list) or len(offset_mm) != 2:
            raise ValueError(f"{context}.offset_mm must be [x_mm, y_mm]")
        offset_x = float(convert_mm_to_inches(float(offset_mm[0])))
        offset_y = float(convert_mm_to_inches(float(offset_mm[1])))
    else:
        offset_x = float(convert_mm_to_inches(float(part.get("x_mm", 0.0))))
        offset_y = float(convert_mm_to_inches(float(part.get("y_mm", 0.0))))
    facing = math.radians(float(part.get("rotation_deg", 0.0)))
    return {
        "part_id": str(part.get("part_id", "") or ""),
        "shape": shape,
        "radius": (float(radius[0]), float(radius[1])),
        "offset": (float(offset_x), float(offset_y)),
        "facing": float(facing),
    }


def _part_local_shape(part_spec: dict):
    shape = str(part_spec["shape"]).lower()
    cx, cy = part_spec["offset"]
    rx, ry = part_spec["radius"]
    facing = float(part_spec["facing"])
    if shape in {"circle", "ellipse"}:
        return create_ellipse((cx, cy), (rx, ry), facing)
    return create_rectangle((cx, cy), (rx, ry), facing)


def _resolve_entry_geometry(entry: dict, *, context: str) -> tuple[BaseType, tuple[float, float], tuple[dict, ...], Optional[float], float]:
    entry_type = str(entry.get("type", "")).strip().lower()
    shape = str(entry.get("shape", "")).strip().lower()

    compound_parts: tuple[dict, ...] = tuple()
    if entry_type == "compound":
        raw_parts = list(entry.get("parts", []) or [])
        part_specs = tuple(_part_to_local_spec(part, context=f"{context}.parts[{idx}]") for idx, part in enumerate(raw_parts))
        part_geoms = [_part_local_shape(spec) for spec in part_specs]
        union_shape = unary_union(part_geoms)
        bounds = union_shape.bounds
        radius = (
            float(max(abs(bounds[0]), abs(bounds[2]))),
            float(max(abs(bounds[1]), abs(bounds[3]))),
        )
        if radius[0] <= 0.0 or radius[1] <= 0.0:
            raise ValueError(f"{context}: compound footprint bounds are degenerate")
        compound_parts = part_specs
        base_type = BaseType.HULL
    elif entry_type == "hull":
        base_type = BaseType.HULL
        radius = _shape_to_radius("hull", entry, context=context)
    elif shape:
        if shape == "circle":
            base_type = BaseType.CIRCULAR
        elif shape == "ellipse":
            base_type = BaseType.ELLIPTICAL
        else:
            base_type = BaseType.HULL
        radius = _shape_to_radius(shape, entry, context=context)
    else:
        raise ValueError(f"{context}: missing type/shape")

    override_height = None
    if "height_mm" in entry:
        override_height = _to_inch(entry.get("height_mm"), field="height_mm", context=context)
    elif entry_type == "compound":
        part_heights = []
        for idx, part in enumerate(entry.get("parts", []) or []):
            if "height_mm" not in part:
                continue
            part_heights.append(
                _to_inch(part.get("height_mm"), field="height_mm", context=f"{context}.parts[{idx}]")
            )
        if part_heights:
            override_height = float(max(part_heights))

    z_offset = 0.0
    if "z_offset_mm" in entry:
        z_offset = _to_non_negative_inch(entry.get("z_offset_mm"), field="z_offset_mm", context=context)

    return base_type, radius, compound_parts, override_height, z_offset


def _estimate_height_from_keywords(
    *,
    unit_keywords: Iterable[str],
    base_minor_diameter: float,
) -> tuple[Optional[float], str]:
    if base_minor_diameter <= 0.0:
        return None, "none"
    normalized = {normalize_geometry_key(k) for k in list(unit_keywords or []) if str(k or "").strip()}

    def _has(keyword: str) -> bool:
        return normalize_geometry_key(keyword) in normalized

    if _has("aircraft"):
        return float(base_minor_diameter * _HEIGHT_AIRCRAFT), "keyword:aircraft"
    if _has("monster") or _has("walker"):
        return float(base_minor_diameter * _HEIGHT_MONSTER_OR_WALKER), "keyword:monster_or_walker"
    if _has("vehicle"):
        return float(base_minor_diameter * _HEIGHT_VEHICLE), "keyword:vehicle"
    if _has("beast") or _has("cavalry"):
        return float(base_minor_diameter * _HEIGHT_BEAST_OR_CAVALRY), "keyword:beast_or_cavalry"
    if _has("infantry") or _has("character"):
        return float(base_minor_diameter * _HEIGHT_INFANTRY_OR_CHARACTER), "keyword:infantry_or_character"
    return None, "none"


def _estimate_flying_base_z_offset(parsed_radius: tuple[float, float]) -> float:
    minor_diameter_in = 2.0 * float(min(parsed_radius))
    if minor_diameter_in <= 0.0:
        return 0.0
    minor_diameter_mm = minor_diameter_in * 25.4
    for max_minor_mm, z_offset_mm in _FLYING_BASE_Z_OFFSET_BY_MINOR_MM:
        if minor_diameter_mm <= float(max_minor_mm) + 1e-6:
            return float(convert_mm_to_inches(float(z_offset_mm)))
    return 0.0


def _normalized_keywords(unit_keywords: Iterable[str]) -> set[str]:
    return {
        normalize_geometry_key(k)
        for k in list(unit_keywords or [])
        if str(k or "").strip()
    }


def _auto_flying_hull_scale(parsed_radius: tuple[float, float]) -> tuple[float, float]:
    minor_diameter_in = 2.0 * float(min(parsed_radius))
    if minor_diameter_in <= 0.0:
        return (1.0, 1.0)
    minor_diameter_mm = minor_diameter_in * 25.4
    for max_minor_mm, scales in _AUTO_FLYING_HULL_SCALE_BY_MINOR_MM:
        if minor_diameter_mm <= float(max_minor_mm) + 1e-6:
            return (float(scales[0]), float(scales[1]))
    return (1.0, 1.0)


def _support_part_from_parsed_base(
    *,
    parsed_base_type: BaseType,
    parsed_radius: tuple[float, float],
) -> dict:
    rx = float(parsed_radius[0])
    ry = float(parsed_radius[1])
    if parsed_base_type == BaseType.CIRCULAR:
        return {
            "part_id": "support_base",
            "shape": "circle",
            "radius": (rx, ry),
            "offset": (0.0, 0.0),
            "facing": 0.0,
        }
    if parsed_base_type == BaseType.ELLIPTICAL:
        return {
            "part_id": "support_base",
            "shape": "ellipse",
            "radius": (rx, ry),
            "offset": (0.0, 0.0),
            "facing": 0.0,
        }
    return {
        "part_id": "support_base",
        "shape": "hull",
        "radius": (rx, ry),
        "offset": (0.0, 0.0),
        "facing": 0.0,
    }


def _auto_flying_vehicle_compound_geometry(
    *,
    parsed_base_type: BaseType,
    parsed_radius: tuple[float, float],
) -> tuple[tuple[float, float], tuple[dict, ...]]:
    support_part = _support_part_from_parsed_base(
        parsed_base_type=parsed_base_type,
        parsed_radius=parsed_radius,
    )
    major_diameter = 2.0 * float(max(parsed_radius))
    minor_diameter = 2.0 * float(min(parsed_radius))
    major_scale, minor_scale = _auto_flying_hull_scale(parsed_radius)
    hull_radius = (
        max(float(parsed_radius[0]), (major_diameter * major_scale) / 2.0),
        max(float(parsed_radius[1]), (minor_diameter * minor_scale) / 2.0),
    )
    hull_part = {
        "part_id": "hull_proxy",
        "shape": "hull",
        "radius": (float(hull_radius[0]), float(hull_radius[1])),
        "offset": (0.0, 0.0),
        "facing": 0.0,
    }
    compound_parts = (support_part, hull_part)

    union_shape = unary_union([_part_local_shape(part) for part in compound_parts])
    bounds = union_shape.bounds
    radius = (
        float(max(abs(bounds[0]), abs(bounds[2]))),
        float(max(abs(bounds[1]), abs(bounds[3]))),
    )
    return radius, compound_parts


def resolve_model_geometry(
    *,
    datasheet_id: Optional[str],
    datasheet_name: str,
    model_name: str,
    unit_keywords: Iterable[str],
    parsed_base_type: BaseType,
    parsed_radius: tuple[float, float],
    parsed_is_flying_base: bool = False,
    catalog_path: Optional[str] = None,
) -> ResolvedModelGeometry:
    catalog = load_model_geometry_catalog(catalog_path)

    guide_entry = _lookup_base_size_guide_entry(
        catalog=catalog,
        datasheet_id=datasheet_id,
        datasheet_name=datasheet_name,
        model_name=model_name,
    )
    guide_classification = str(guide_entry.get("classification", "")).strip().lower()
    preferred_key = str(guide_entry.get("geometry_key", "")).strip() or None

    unit_key = _lookup_unit_key(
        catalog=catalog,
        datasheet_id=datasheet_id,
        datasheet_name=datasheet_name,
        model_name=model_name,
        preferred_key=preferred_key,
    )
    entry = dict((catalog.get("units", {}) or {}).get(unit_key, {}) or {}) if unit_key else {}

    requires_manual = bool(guide_entry.get("requires_manual_geometry", False))
    if guide_classification in {"hull", "unique"}:
        requires_manual = True
    if requires_manual and not entry:
        raise ValueError(
            f"Missing model geometry override for '{datasheet_name}' ({datasheet_id or 'no id'}). "
            "Base Size Guide classification requires manual geometry."
        )

    base_type = parsed_base_type
    radius = (float(parsed_radius[0]), float(parsed_radius[1]))
    compound_parts: tuple[dict, ...] = tuple()
    override_height: Optional[float] = None
    z_offset = 0.0
    entry_has_z_offset = False
    geometry_source = "parsed_base"

    if guide_classification == "hull" and base_type != BaseType.HULL and not entry:
        base_type = BaseType.HULL
        geometry_source = "base_size_guide:hull"

    if entry:
        context = f"model_geometry_overrides.units.{unit_key}"
        base_type, radius, compound_parts, override_height, z_offset = _resolve_entry_geometry(entry, context=context)
        entry_has_z_offset = "z_offset_mm" in entry
        geometry_source = f"geometry_override:{unit_key}"

    settings = dict(catalog.get("settings", {}) or {})
    hull_proxy_policy = str(settings.get("hull_proxy_policy", "")).strip().lower()
    if (
        not entry
        and bool(parsed_is_flying_base)
        and hull_proxy_policy == "bounding"
    ):
        normalized_keywords = _normalized_keywords(unit_keywords)
        has_vehicle = "vehicle" in normalized_keywords
        has_monster = "monster" in normalized_keywords
        support_minor_mm = 2.0 * float(min(parsed_radius)) * 25.4
        if (has_vehicle or has_monster) and support_minor_mm >= _AUTO_FLYING_PROXY_MIN_SUPPORT_BASE_MM - 1e-6:
            auto_radius, auto_parts = _auto_flying_vehicle_compound_geometry(
                parsed_base_type=parsed_base_type,
                parsed_radius=(float(parsed_radius[0]), float(parsed_radius[1])),
            )
            base_type = BaseType.HULL
            radius = auto_radius
            compound_parts = auto_parts
            geometry_source = "auto_flying_vehicle_compound"

    base_minor_diameter = 2.0 * float(min(radius))
    heuristic_height, heuristic_source = _estimate_height_from_keywords(
        unit_keywords=unit_keywords,
        base_minor_diameter=base_minor_diameter,
    )

    if override_height is not None:
        resolved_height = float(override_height)
        height_source = "override"
    elif heuristic_height is not None:
        resolved_height = float(heuristic_height)
        height_source = heuristic_source
    else:
        resolved_height = float(base_minor_diameter)
        height_source = "fallback:base_minor_diameter"
        if base_type == BaseType.HULL:
            logger.warning(
                "Hull model '%s' (%s) resolved without override/keyword heuristic; falling back to minor diameter height %.2f\".",
                datasheet_name,
                datasheet_id or "no id",
                resolved_height,
            )

    if bool(parsed_is_flying_base) and not entry_has_z_offset and z_offset <= 0.0:
        # Flying stem height should follow the parsed support base, not an override
        # hull/compound footprint that may be substantially larger.
        z_offset = _estimate_flying_base_z_offset(
            (float(parsed_radius[0]), float(parsed_radius[1]))
        )

    return ResolvedModelGeometry(
        base_type=base_type,
        radius=(float(radius[0]), float(radius[1])),
        model_height=resolved_height,
        z_offset=float(z_offset),
        compound_parts=compound_parts,
        geometry_source=geometry_source,
        height_source=height_source,
    )
