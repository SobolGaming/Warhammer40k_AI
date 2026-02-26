from types import SimpleNamespace

from warhammer40k_ai.UI.phases.phase_manager import DeploymentPhaseHandler


def test_deployment_phase_handler_move_decision_proxy_delegates_to_phase_manager() -> None:
    calls = []

    def _proxy(*args, **kwargs):
        calls.append((args, kwargs))

    handler = DeploymentPhaseHandler.__new__(DeploymentPhaseHandler)
    handler.game_view = SimpleNamespace(phase_manager=SimpleNamespace(_request_move_unit_decision=_proxy))

    handler._request_move_unit_decision(
        unit="unit",
        movement_type="deploy",
        callback="callback",
        max_distance=0.0,
        target_unit="target",
        placement_validator="validator",
        decision_request="request",
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("unit", "deploy", "callback")
    assert kwargs == {
        "max_distance": 0.0,
        "target_unit": "target",
        "placement_validator": "validator",
        "decision_request": "request",
    }
