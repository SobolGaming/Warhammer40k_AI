from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYER1_ARMY = "army_lists/chaos_test.txt"
PLAYER2_ARMY = "army_lists/aeldari_test.txt"


def _run_script(script: str, *, env: dict[str, str] | None = None, timeout: int = 180) -> str:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        [
            sys.executable,
            script,
            "--player1-army",
            PLAYER1_ARMY,
            "--player2-army",
            PLAYER2_ARMY,
        ],
        cwd=REPO_ROOT,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout


@pytest.mark.smoke
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.ui
def test_local_ui_smoke_script() -> None:
    output = _run_script(
        "scripts/smoke_ui_local.py",
        env={
            "SDL_VIDEODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        },
    )

    assert "local_ui_smoke=ok" in output
    assert "deployment_decision=true" in output


@pytest.mark.smoke
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.network
def test_network_loopback_smoke_script() -> None:
    output = _run_script("scripts/smoke_network_loopback.py")

    assert "network_loopback_smoke=ok" in output
    assert "deployment_resolved=true" in output


@pytest.mark.smoke
@pytest.mark.integration
@pytest.mark.slow
def test_snapshot_plan_smoke_script() -> None:
    output = _run_script("scripts/smoke_snapshot_plans.py")

    assert "snapshot_plan_smoke=ok" in output
