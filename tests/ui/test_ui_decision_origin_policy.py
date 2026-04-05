from __future__ import annotations

from pathlib import Path

from warhammer40k_ai.engine import ui_decision_bridge


UI_ROOT = Path("src/warhammer40k_ai/UI")
FORBIDDEN_PATTERNS = (
    "DecisionRequest.create(",
    ".request_decision(",
    "create_decision_request(",
    "queue_existing_decision_request(",
    "queue_decision_request(",
    "build_leader_attachment_requests(",
    "build_support_artillery_attachment_requests(",
    "build_transport_assignment_requests(",
    "build_reserves_allocation_request(",
    "build_player_color_selection_requests(",
    "build_patrol_squad_requests(",
    "build_shadow_assignment_requests(",
    "build_scout_move_request(",
    "build_start_of_round_request(",
    "build_command_phase_bearer_request(",
    "request_mission_selection(",
)


def test_ui_modules_do_not_bypass_engine_decision_bridge() -> None:
    """UI code must not originate DecisionRequests or enqueue them."""
    violations: list[str] = []
    for path in sorted(UI_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                violations.append(f"{path}: contains `{pattern}`")
    assert not violations, "UI decision-origin policy violations:\n" + "\n".join(violations)


def test_ui_decision_bridge_does_not_expose_enqueue_helpers() -> None:
    """Bridge module is reader-only for UI-facing usage."""
    assert not hasattr(ui_decision_bridge, "queue_decision_request")
    assert not hasattr(ui_decision_bridge, "_create_decision_request")
