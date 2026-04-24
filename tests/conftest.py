from __future__ import annotations

import os
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]

_UI_DEPENDENT_TEST_PATHS = {
    "tests/ai/test_main_profile_cli.py",
    "tests/engine/test_battle_phase_handler_init.py",
    "tests/engine/test_deployment_phase_handler_proxy.py",
    "tests/engine/test_deployment_zone_player_colors.py",
    "tests/engine/test_phase_flow_contracts.py",
    "tests/network/test_session_presentation_orchestrator.py",
    "tests/replay/test_replay_viewer.py",
    "tests/rules/test_human_interface_reserves.py",
    "tests/rules/test_individual_model_movement_floor_selection.py",
    "tests/rules/test_pile_in_visualization.py",
    "tests/rules/test_range_renderer_weapon_cache.py",
    "tests/rules/test_roll_explanation.py",
    "tests/rules/test_target_model_selection_attached_precision.py",
}

_UI_DEPENDENT_TEXT_MARKERS = (
    "import pygame",
    "from pygame",
    "warhammer40k_ai.UI",
)


def _relative_repo_path(path: object) -> str:
    candidate = Path(str(path)).resolve()
    if candidate == _REPO_ROOT or _REPO_ROOT in candidate.parents:
        return candidate.relative_to(_REPO_ROOT).as_posix()
    return candidate.as_posix()


def _is_ui_test_path(path: object) -> bool:
    relative = _relative_repo_path(path)
    if relative.startswith("tests/ui/"):
        return True
    if relative in _UI_DEPENDENT_TEST_PATHS:
        return True
    candidate = _REPO_ROOT / relative
    if not relative.startswith("tests/") or not relative.endswith(".py") or not candidate.is_file():
        return False
    text = candidate.read_text(encoding="utf-8")
    return any(marker in text for marker in _UI_DEPENDENT_TEXT_MARKERS)


def _skip_ui_collection(config: pytest.Config) -> bool:
    if os.environ.get("WARHAMMER40K_AI_SKIP_UI_TESTS") == "1":
        return True
    markexpr = str(getattr(config.option, "markexpr", "") or "")
    normalized = "".join(markexpr.lower().split())
    return "notui" in normalized


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    return _skip_ui_collection(config) and _is_ui_test_path(collection_path)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        if _is_ui_test_path(item.path):
            item.add_marker(pytest.mark.ui)
