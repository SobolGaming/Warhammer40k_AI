from __future__ import annotations

from typing import Any


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def snapshot_unit_model_state(unit: object) -> list[tuple[object, float, float, float, float]]:
    snapshot: list[tuple[object, float, float, float, float]] = []
    for model in list(getattr(unit, "models", []) or []):
        getter = getattr(model, "get_location", None)
        base = getattr(model, "model_base", None)
        if callable(getter):
            location = tuple(getter() or ())
            x = _safe_float(location[0] if len(location) > 0 else getattr(base, "x", 0.0), getattr(base, "x", 0.0))
            y = _safe_float(location[1] if len(location) > 1 else getattr(base, "y", 0.0), getattr(base, "y", 0.0))
            z = _safe_float(location[2] if len(location) > 2 else getattr(base, "z", 0.0), getattr(base, "z", 0.0))
            facing = _safe_float(
                location[3] if len(location) > 3 else getattr(base, "facing", 0.0),
                getattr(base, "facing", 0.0),
            )
        else:
            x = _safe_float(getattr(base, "x", 0.0), 0.0)
            y = _safe_float(getattr(base, "y", 0.0), 0.0)
            z = _safe_float(getattr(base, "z", 0.0), 0.0)
            facing = _safe_float(getattr(base, "facing", 0.0), 0.0)
        snapshot.append((model, x, y, z, facing))
    return snapshot


def restore_unit_model_state(snapshot: list[tuple[object, float, float, float, float]]) -> None:
    for model, x, y, z, facing in list(snapshot or []):
        setter = getattr(model, "set_location", None)
        if callable(setter):
            setter(float(x), float(y), float(z), float(facing))
            continue
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        base.x = float(x)
        base.y = float(y)
        base.z = float(z)
        base.facing = float(facing)


def calculate_prospective_model_positions(
    unit: object,
    start_x: float,
    start_y: float,
    game_map: object,
    *,
    avoid_friendly_units: bool = True,
    boundary_repulsors: Any = None,
) -> list[tuple[float, float, float, float]]:
    calculate = getattr(unit, "calculate_model_positions", None)
    if not callable(calculate):
        return []
    snapshot = snapshot_unit_model_state(unit)
    try:
        model_positions = calculate(
            float(start_x),
            float(start_y),
            game_map,
            avoid_friendly_units=avoid_friendly_units,
            boundary_repulsors=boundary_repulsors,
        )
        normalized: list[tuple[float, float, float, float]] = []
        for entry in list(model_positions or []):
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                return []
            x = _safe_float(entry[0], 0.0)
            y = _safe_float(entry[1], 0.0)
            z = _safe_float(entry[2] if len(entry) > 2 else 0.0, 0.0)
            facing = _safe_float(entry[3] if len(entry) > 3 else 0.0, 0.0)
            normalized.append((x, y, z, facing))
        return normalized
    finally:
        restore_unit_model_state(snapshot)
