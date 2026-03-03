from __future__ import annotations

import pytest

from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker


class _StubUnit:
    def __init__(self, unit_id: str, *, must_start_in_reserves: bool) -> None:
        self._id = unit_id
        self.id = unit_id
        self._must_start_in_reserves = bool(must_start_in_reserves)

    def must_start_in_reserves(self) -> bool:
        return bool(self._must_start_in_reserves)


class _StubArmy:
    def __init__(self, units) -> None:
        self.units = list(units)
        self.validated_payload = None

    def validate_reserves_decisions(self, decisions):
        self.validated_payload = dict(decisions)
        return {"valid": True}


class _StubPlayer:
    def __init__(self, army) -> None:
        self._army = army

    def get_army(self):
        return self._army


def test_forced_only_reserve_policy_keeps_optional_units_deployed() -> None:
    required = _StubUnit("unit:required", must_start_in_reserves=True)
    optional = _StubUnit("unit:optional", must_start_in_reserves=False)
    army = _StubArmy([required, optional])
    player = _StubPlayer(army)

    maker = DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="forced_only")
    decisions = maker.declare_reserves(player)

    assert decisions == {
        "unit:required": "reserves",
        "unit:optional": "deploy",
    }
    assert army.validated_payload == decisions


def test_invalid_reserve_policy_raises_value_error() -> None:
    with pytest.raises(ValueError):
        DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="unknown_policy")

