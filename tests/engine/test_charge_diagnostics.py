from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.charge_diagnostics import charge_failure_diagnostics


class _DistanceMap:
    def __init__(self, distances: dict[str, float]) -> None:
        self.distances = dict(distances)

    def get_distance_between_units(self, _charging_unit, target_unit) -> float:
        return float(self.distances[str(target_unit.id)])


def test_charge_failure_diagnostics_classifies_outside_declaration_range() -> None:
    charger = SimpleNamespace(id="charger")
    target = SimpleNamespace(id="target")
    diagnostics = charge_failure_diagnostics(
        _DistanceMap({"target": 12.25}),
        charger,
        [target],
        max_distance=12,
        solver_failure_reason="no_legal_charge_move",
    )

    assert diagnostics["within_declaration_range"] is False
    assert diagnostics["failure_stage"] == "declaration_range"
    assert diagnostics["diagnostic_reason"] == "target_outside_declaration_range"
    assert diagnostics["target_distances"][0]["distance"] == 12.25


def test_charge_failure_diagnostics_classifies_roll_distance_before_endpoint_geometry() -> None:
    charger = SimpleNamespace(id="charger")
    target = SimpleNamespace(id="target")
    diagnostics = charge_failure_diagnostics(
        _DistanceMap({"target": 9.5}),
        charger,
        [target],
        max_distance=7,
        solver_failure_reason="no_legal_charge_move",
    )

    assert diagnostics["within_declaration_range"] is True
    assert diagnostics["failure_stage"] == "charge_roll_distance"
    assert diagnostics["diagnostic_reason"] == "charge_roll_insufficient_by_distance"
    assert diagnostics["required_charge_distance_estimate"] == 8.5


def test_charge_failure_diagnostics_classifies_endpoint_geometry_when_roll_can_reach() -> None:
    charger = SimpleNamespace(id="charger")
    target = SimpleNamespace(id="target")
    diagnostics = charge_failure_diagnostics(
        _DistanceMap({"target": 5.0}),
        charger,
        [target],
        max_distance=7,
        solver_failure_reason="no_legal_charge_move",
    )

    assert diagnostics["within_declaration_range"] is True
    assert diagnostics["failure_stage"] == "endpoint_geometry"
    assert diagnostics["diagnostic_reason"] == "no_legal_charge_endpoint"
