from __future__ import annotations

from pathlib import Path

import pytest

from warhammer40k_ai.engine.headless_setup_benchmark import run_setup_only_headless_benchmark


@pytest.mark.integration
@pytest.mark.slow
def test_headless_setup_benchmark_completes_representative_2000_point_rosters() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report = run_setup_only_headless_benchmark(
        player1_army_file=str(repo_root / "army_lists" / "Aeldari_Warhost_2000.txt"),
        player2_army_file=str(repo_root / "army_lists" / "WE_Daemonkin_2000.txt"),
        reserve_policy="forced_only",
    )

    assert str(report.get("last_completed_setup_phase", "") or "") == "DEPLOY_ARMIES"
    assert str(report.get("current_setup_phase", "") or "") == "REDEPLOY_UNITS"
    deployment_summary = dict(report.get("deployment_summary", {}) or {})
    assert int(deployment_summary.get("unit_count", 0) or 0) > 0
