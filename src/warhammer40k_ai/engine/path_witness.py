from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id

PATH_WITNESS_SCHEMA_VERSION = "1.0.0"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _extract_pose(entry: dict[str, Any]) -> tuple[float, float, float, float]:
    position = list(dict(entry or {}).get("position") or [0.0, 0.0, 0.0])
    while len(position) < 3:
        position.append(0.0)
    return (
        _safe_float(position[0], 0.0),
        _safe_float(position[1], 0.0),
        _safe_float(position[2], 0.0),
        _safe_float(dict(entry or {}).get("facing", 0.0), 0.0),
    )


def current_model_positions(unit: object) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for model in sorted(list(getattr(unit, "models", []) or []), key=lambda m: str(get_entity_id(m))):
        is_alive_value = getattr(model, "is_alive", True)
        is_alive = bool(is_alive_value() if callable(is_alive_value) else is_alive_value)
        if not is_alive:
            continue
        getter = getattr(model, "get_location", None)
        if callable(getter):
            loc = getter()
            x = _safe_float(loc[0] if len(loc) > 0 else 0.0)
            y = _safe_float(loc[1] if len(loc) > 1 else 0.0)
            z = _safe_float(loc[2] if len(loc) > 2 else 0.0)
            facing = _safe_float(loc[3] if len(loc) > 3 else 0.0)
        else:
            base = getattr(model, "model_base", None)
            x = _safe_float(getattr(base, "x", 0.0), 0.0)
            y = _safe_float(getattr(base, "y", 0.0), 0.0)
            z = _safe_float(getattr(base, "z", 0.0), 0.0)
            facing = _safe_float(getattr(base, "facing", 0.0), 0.0)
        base = getattr(model, "model_base", None)
        radius = list(getattr(base, "radius", []) or [])
        if len(radius) < 2:
            r = _safe_float(getattr(base, "get_radius", lambda: 0.0)(), 0.0) if base is not None else 0.0
            radius = [r, r]
        base_type = str(getattr(getattr(base, "base_type", None), "name", "CIRCULAR"))
        positions.append(
            {
                "model_id": str(get_entity_id(model)),
                "position": [x, y, z],
                "facing": facing,
                "radius": [float(radius[0]), float(radius[1])],
                "base_type": base_type,
            }
        )
    return positions


def build_model_path_witness(
    *,
    model_positions: list[dict[str, Any]],
    movement_type: str,
    start_positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    start_by_id = {
        str(entry.get("model_id", "") or ""): entry for entry in list(start_positions or []) if entry is not None
    }
    models: list[dict[str, Any]] = []
    corridors: list[dict[str, Any]] = []
    for entry in sorted(list(model_positions or []), key=lambda item: str(item.get("model_id", ""))):
        model_id = str(entry.get("model_id", "") or "")
        start_entry = start_by_id.get(model_id, entry)
        sx, sy, sz, sf = _extract_pose(start_entry)
        ex, ey, ez, ef = _extract_pose(entry)
        path = [
            {
                "kind": "translate",
                "start": [float(sx), float(sy), float(sz)],
                "end": [float(ex), float(ey), float(ez)],
            },
            {
                "kind": "pivot",
                "start_facing": float(sf),
                "end_facing": float(ef),
            },
        ]
        models.append(
            {
                "model_id": model_id,
                "path": path,
                "final_pose": [float(ex), float(ey), float(ez), float(ef)],
            }
        )
        corridors.append(
            {
                "model_id": model_id,
                "start": [float(sx), float(sy), float(sz)],
                "end": [float(ex), float(ey), float(ez)],
                "clearance_class": "default",
            }
        )
    return {
        "schema_version": PATH_WITNESS_SCHEMA_VERSION,
        "movement_type": str(movement_type or ""),
        "corridors": corridors,
        "models": models,
    }


def build_model_path_witness_for_unit(
    *,
    unit: object,
    model_positions: list[dict[str, Any]],
    movement_type: str,
) -> dict[str, Any]:
    return build_model_path_witness(
        model_positions=list(model_positions or []),
        movement_type=movement_type,
        start_positions=current_model_positions(unit),
    )


def validate_witness_contiguity(
    witness: dict[str, Any],
    model_positions: list[dict[str, Any]],
    *,
    tolerance: float = 1e-4,
) -> list[str]:
    errors: list[str] = []
    expected_by_id = {
        str(entry.get("model_id", "") or ""): entry for entry in list(model_positions or []) if entry is not None
    }
    models = list(dict(witness or {}).get("models", []) or [])
    for model_entry in models:
        model_id = str(dict(model_entry or {}).get("model_id", "") or "")
        path = list(dict(model_entry or {}).get("path", []) or [])
        if not path:
            errors.append(f"PathWitness missing path for model_id={model_id}.")
            continue
        translate = dict(path[0] or {})
        start = list(translate.get("start", []) or [])
        end = list(translate.get("end", []) or [])
        if len(start) < 3 or len(end) < 3:
            errors.append(f"PathWitness translate step missing coordinates for model_id={model_id}.")
            continue
        pivot = dict(path[1] or {}) if len(path) > 1 else {}
        if pivot:
            start_facing = _safe_float(pivot.get("start_facing", 0.0), 0.0)
            end_facing = _safe_float(pivot.get("end_facing", 0.0), 0.0)
            if abs(start_facing - end_facing) > 360.0:
                errors.append(f"PathWitness pivot invalid for model_id={model_id}.")
        final_pose = list(dict(model_entry or {}).get("final_pose", []) or [])
        if len(final_pose) < 4:
            errors.append(f"PathWitness final_pose missing values for model_id={model_id}.")
            continue
        if (
            abs(float(end[0]) - float(final_pose[0])) > tolerance
            or abs(float(end[1]) - float(final_pose[1])) > tolerance
            or abs(float(end[2]) - float(final_pose[2])) > tolerance
        ):
            errors.append(f"PathWitness final_pose does not match segment end for model_id={model_id}.")
        expected = expected_by_id.get(model_id)
        if expected is None:
            continue
        ex, ey, ez, ef = _extract_pose(expected)
        if (
            abs(float(final_pose[0]) - ex) > tolerance
            or abs(float(final_pose[1]) - ey) > tolerance
            or abs(float(final_pose[2]) - ez) > tolerance
            or abs(float(final_pose[3]) - ef) > tolerance
        ):
            errors.append(f"PathWitness final_pose does not match move payload for model_id={model_id}.")
    return errors


def _distance_point_to_segment_2d(
    point_x: float,
    point_y: float,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> float:
    seg_x = float(end_x) - float(start_x)
    seg_y = float(end_y) - float(start_y)
    if abs(seg_x) < 1e-9 and abs(seg_y) < 1e-9:
        dx = float(point_x) - float(start_x)
        dy = float(point_y) - float(start_y)
        return (dx * dx + dy * dy) ** 0.5
    t = ((float(point_x) - float(start_x)) * seg_x + (float(point_y) - float(start_y)) * seg_y) / (seg_x * seg_x + seg_y * seg_y)
    t = max(0.0, min(1.0, t))
    proj_x = float(start_x) + t * seg_x
    proj_y = float(start_y) + t * seg_y
    dx = float(point_x) - proj_x
    dy = float(point_y) - proj_y
    return (dx * dx + dy * dy) ** 0.5


def detect_normal_move_engagement_crossing(
    *,
    start_positions: list[dict[str, Any]],
    end_positions: list[dict[str, Any]],
    enemy_bases: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    starts = {str(entry.get("model_id", "") or ""): entry for entry in list(start_positions or []) if entry is not None}
    ends = {str(entry.get("model_id", "") or ""): entry for entry in list(end_positions or []) if entry is not None}
    for model_id, end_entry in sorted(ends.items()):
        start_entry = starts.get(model_id)
        if start_entry is None:
            continue
        sx, sy, sz, _sf = _extract_pose(start_entry)
        ex, ey, ez, _ef = _extract_pose(end_entry)
        own_radius = _safe_float(end_entry.get("radius", 0.0), 0.0)
        for enemy in list(enemy_bases or []):
            clearance = float(ENGAGEMENT_RANGE_HORIZONTAL) + own_radius + _safe_float(enemy.get("radius", 0.0), 0.0)
            dist_2d = _distance_point_to_segment_2d(
                _safe_float(enemy.get("x", 0.0), 0.0),
                _safe_float(enemy.get("y", 0.0), 0.0),
                sx,
                sy,
                ex,
                ey,
            )
            if dist_2d > clearance:
                continue
            enemy_z = _safe_float(enemy.get("z", 0.0), 0.0)
            min_z = min(sz, ez) - float(ENGAGEMENT_RANGE_VERTICAL)
            max_z = max(sz, ez) + float(ENGAGEMENT_RANGE_VERTICAL)
            if enemy_z < min_z or enemy_z > max_z:
                continue
            errors.append(f"Move path crosses engagement range of enemy model for model_id={model_id}.")
            break
    return errors


def _base_clearance_thresholds(entry: dict[str, Any]) -> tuple[float, float]:
    radius = list(dict(entry or {}).get("radius", []) or [])
    if len(radius) < 2:
        r = _safe_float(dict(entry or {}).get("radius", 0.0), 0.0)
        radius = [r, r]
    a = abs(_safe_float(radius[0], 0.0))
    b = abs(_safe_float(radius[1], 0.0))
    if a < b:
        a, b = b, a
    base_type = str(dict(entry or {}).get("base_type", "ELLIPTICAL") or "ELLIPTICAL").upper()
    if base_type == "HULL":
        w = min(a, b)
        l = max(a, b)
        upper = (l * l + w * w) ** 0.5
        return (w, upper)
    return (b, a)


def _normalize_yaw_delta(start_facing: float, end_facing: float) -> float:
    delta = abs(float(end_facing) - float(start_facing)) % 360.0
    return min(delta, 360.0 - delta)


def detect_tight_clearance_orientation_violations(
    *,
    start_positions: list[dict[str, Any]],
    end_positions: list[dict[str, Any]],
    enemy_bases: list[dict[str, Any]],
    yaw_band_deg: float = 15.0,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    profiles: dict[str, dict[str, Any]] = {}
    starts = {str(entry.get("model_id", "") or ""): entry for entry in list(start_positions or []) if entry is not None}
    ends = {str(entry.get("model_id", "") or ""): entry for entry in list(end_positions or []) if entry is not None}
    for model_id, end_entry in sorted(ends.items()):
        start_entry = starts.get(model_id)
        if start_entry is None:
            continue
        sx, sy, sz, sf = _extract_pose(start_entry)
        ex, ey, ez, ef = _extract_pose(end_entry)
        tight_low, tight_high = _base_clearance_thresholds(end_entry)
        length_2d = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
        if length_2d <= 1e-9:
            profiles[model_id] = {
                "min_clearance": float("inf"),
                "tight_intervals": [],
                "adaptive_steps": [],
            }
            continue
        t = 0.0
        min_clearance = float("inf")
        tight_intervals: list[dict[str, float]] = []
        adaptive_steps: list[dict[str, float]] = []
        open_interval_start: float | None = None
        while t < 1.0:
            px = sx + (ex - sx) * t
            py = sy + (ey - sy) * t
            pz = sz + (ez - sz) * t
            nearest = float("inf")
            for enemy in list(enemy_bases or []):
                dist = _distance_point_to_segment_2d(
                    _safe_float(enemy.get("x", 0.0), 0.0),
                    _safe_float(enemy.get("y", 0.0), 0.0),
                    px,
                    py,
                    px,
                    py,
                ) - _safe_float(enemy.get("radius", 0.0), 0.0)
                enemy_z = _safe_float(enemy.get("z", 0.0), 0.0)
                if abs(enemy_z - pz) > float(ENGAGEMENT_RANGE_VERTICAL):
                    continue
                nearest = min(nearest, dist)
            if nearest == float("inf"):
                nearest = 9999.0
            min_clearance = min(min_clearance, nearest)
            is_tight = nearest >= tight_low and nearest < tight_high
            is_very_tight = nearest < tight_low
            if is_tight and open_interval_start is None:
                open_interval_start = t
            if not is_tight and open_interval_start is not None:
                tight_intervals.append({"start_t": float(open_interval_start), "end_t": float(t)})
                open_interval_start = None
            step_inches = 0.5
            if is_tight:
                step_inches = 0.25
            if is_very_tight:
                step_inches = 0.1
            step_t = max(0.01, min(1.0, step_inches / max(length_2d, 1e-6)))
            adaptive_steps.append({"t": float(t), "step_inches": float(step_inches), "clearance": float(nearest)})
            t += step_t
        if open_interval_start is not None:
            tight_intervals.append({"start_t": float(open_interval_start), "end_t": 1.0})
        yaw_delta = _normalize_yaw_delta(sf, ef)
        if tight_intervals and yaw_delta > float(yaw_band_deg):
            errors.append(
                f"Move path violates tight-clearance yaw constraint for model_id={model_id} "
                f"(delta={yaw_delta:.1f}deg, limit={float(yaw_band_deg):.1f}deg)."
            )
        profiles[model_id] = {
            "min_clearance": float(min_clearance),
            "tight_intervals": tight_intervals,
            "adaptive_steps": adaptive_steps,
            "yaw_delta": float(yaw_delta),
            "yaw_band_deg": float(yaw_band_deg),
        }
    return errors, profiles


@dataclass
class PathWitnessStore:
    _records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put(self, witness: dict[str, Any]) -> str:
        payload = dict(witness or {})
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        ref = f"pathwitness://{digest}"
        self._records[ref] = payload
        return ref

    def get(self, ref: str) -> dict[str, Any] | None:
        key = str(ref or "")
        if not key:
            return None
        value = self._records.get(key)
        if value is None:
            return None
        return dict(value)
