from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from warhammer40k_ai.roster.army import parse_army_list_text
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.mark.integration
def test_synthesize_roster_cli_writes_report_blueprint_and_roundtrip_export(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "synth"
    subprocess.run(
        [
            sys.executable,
            "scripts/synthesize_roster.py",
            "--max-points",
            "500",
            "--faction",
            "World Eaters",
            "--detachment",
            "Khorne Daemonkin",
            "--style",
            "melee offensive daemonkin",
            "--include-unit",
            "Lord on Juggernaut",
            "--top-k",
            "1",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    report_path = output_dir / "synthesis_report.json"
    blueprint_path = output_dir / "candidate_01_blueprint.json"
    army_list_path = output_dir / "candidate_01_army_list.txt"
    muster_record_path = output_dir / "candidate_01_muster_record.json"
    assert report_path.exists()
    assert blueprint_path.exists()
    assert army_list_path.exists()
    assert muster_record_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    muster_record = json.loads(muster_record_path.read_text(encoding="utf-8"))
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert muster_record["source_tag"] == "roster_synthesis"
    assert muster_record["army_blueprint_hash"] == candidate["army_blueprint_hash"]
    parsed_army = parse_army_list_text(
        army_list_path.read_text(encoding="utf-8"),
        WahaHelper(),
        list_name="cli_synthesized_roster",
    )
    parsed_army.validate()
    assert parsed_army.get_total_points() == candidate["points"]
