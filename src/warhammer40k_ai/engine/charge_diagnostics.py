from __future__ import annotations

import math
from typing import Any, Iterable

from ..utility.entity_ids import get_entity_id


CHARGE_DECLARATION_RANGE_INCHES = 12.0
CHARGE_DECLARATION_EPSILON = 1e-6
CHARGE_ENGAGEMENT_RANGE_ESTIMATE_INCHES = 1.0


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _distance_payload_value(value: float) -> float:
    return round(float(value), 6)


def charge_target_distance_rows(
    game_map: object,
    charging_unit: object,
    target_units: Iterable[object],
) -> list[dict[str, Any]]:
    distance_between_units = getattr(game_map, "get_distance_between_units", None)
    rows: list[dict[str, Any]] = []
    for target in list(target_units or []):
        target_id = str(get_entity_id(target) or "").strip()
        if not target_id:
            continue
        row: dict[str, Any] = {"target_unit_id": target_id}
        if callable(distance_between_units):
            try:
                distance = _finite_float(distance_between_units(charging_unit, target))
            except (AttributeError, TypeError, ValueError):
                distance = None
            if distance is not None:
                required_estimate = max(0.0, distance - CHARGE_ENGAGEMENT_RANGE_ESTIMATE_INCHES)
                row["distance"] = _distance_payload_value(distance)
                row["within_declaration_range"] = bool(
                    distance <= CHARGE_DECLARATION_RANGE_INCHES + CHARGE_DECLARATION_EPSILON
                )
                row["required_charge_distance_estimate"] = _distance_payload_value(required_estimate)
        rows.append(row)
    return rows


def charge_failure_diagnostics(
    game_map: object,
    charging_unit: object,
    target_units: Iterable[object],
    *,
    max_distance: object,
    solver_failure_reason: str,
) -> dict[str, Any]:
    rows = charge_target_distance_rows(game_map, charging_unit, target_units)
    if not rows:
        return {}

    diagnostics: dict[str, Any] = {
        "declaration_range_limit": CHARGE_DECLARATION_RANGE_INCHES,
        "target_distances": rows,
    }
    charge_roll = _finite_float(max_distance)
    if charge_roll is not None:
        diagnostics["charge_roll"] = _distance_payload_value(charge_roll)

    distances = [
        float(row["distance"])
        for row in rows
        if "distance" in row and _finite_float(row.get("distance")) is not None
    ]
    required_estimates = [
        float(row["required_charge_distance_estimate"])
        for row in rows
        if "required_charge_distance_estimate" in row
        and _finite_float(row.get("required_charge_distance_estimate")) is not None
    ]
    if distances:
        diagnostics["minimum_target_distance"] = _distance_payload_value(min(distances))
        diagnostics["maximum_target_distance"] = _distance_payload_value(max(distances))
    if required_estimates:
        diagnostics["required_charge_distance_estimate"] = _distance_payload_value(max(required_estimates))

    all_distances_known = len(distances) == len(rows)
    if not all_distances_known:
        diagnostics["failure_stage"] = "target_distance_unknown"
        return diagnostics
    all_within_declaration_range = all(bool(row.get("within_declaration_range", False)) for row in rows)
    diagnostics["within_declaration_range"] = all_within_declaration_range
    if not all_within_declaration_range:
        diagnostics["failure_stage"] = "declaration_range"
        diagnostics["diagnostic_reason"] = "target_outside_declaration_range"
        return diagnostics
    if charge_roll is not None and required_estimates:
        required_distance = max(required_estimates)
        if required_distance > charge_roll + CHARGE_DECLARATION_EPSILON:
            diagnostics["failure_stage"] = "charge_roll_distance"
            diagnostics["diagnostic_reason"] = "charge_roll_insufficient_by_distance"
            return diagnostics

    diagnostics["failure_stage"] = "endpoint_geometry"
    if str(solver_failure_reason or "") == "no_legal_charge_move":
        diagnostics["diagnostic_reason"] = "no_legal_charge_endpoint"
    return diagnostics
