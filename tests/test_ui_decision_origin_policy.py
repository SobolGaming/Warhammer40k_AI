from __future__ import annotations

from pathlib import Path


UI_ROOT = Path("src/warhammer40k_ai/UI")
FORBIDDEN_PATTERNS = (
    "DecisionRequest.create(",
    ".request_decision(",
    "create_decision_request(",
    "queue_existing_decision_request(",
    "queue_decision_request(",
)


def test_ui_modules_do_not_bypass_engine_decision_bridge() -> None:
    """UI code must route decision creation/enqueue through engine bridge helpers."""
    violations: list[str] = []
    for path in sorted(UI_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                violations.append(f"{path}: contains `{pattern}`")
    assert not violations, "UI decision-origin policy violations:\n" + "\n".join(violations)
