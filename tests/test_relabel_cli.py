from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_relabel_cli_writes_relabel_fields(tmp_path: Path) -> None:
    input_path = tmp_path / "decision_records.json"
    output_path = tmp_path / "decision_records_relabeled.json"
    input_document = [
        {
            "decision_id": "decision_1",
            "rules_bundle": {
                "core_rules_id": "core_old",
                "rules_commentary_id": "commentary_old",
                "mission_pack_id": "mission_old",
                "terrain_pack_id": "terrain_old",
                "dataslate_id": "dataslate_old",
                "points_id": "points_old",
                "faction_pack_id": "faction_old",
                "detachment_pack_id": "detachment_old",
            },
            "rules_bundle_id": "rules_bundle:oldbundle",
            "candidates": [
                {
                    "action_id": "action_yes",
                    "params": {"choice": True},
                    "metadata": {},
                }
            ],
            "mask": [True],
            "chosen_action_id": "action_yes",
            "valid": True,
        }
    ]
    input_path.write_text(
        json.dumps(input_document, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "relabel_decision_records.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--core-rules-id",
        "core_new",
        "--rules-commentary-id",
        "commentary_new",
        "--mission-pack-id",
        "mission_new",
        "--terrain-pack-id",
        "terrain_new",
        "--dataslate-id",
        "dataslate_new",
        "--points-id",
        "points_new",
        "--faction-pack-id",
        "faction_new",
        "--detachment-pack-id",
        "detachment_new",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0
    assert output_path.exists()

    output_document = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(output_document, list)
    assert len(output_document) == 1
    relabeled = dict(output_document[0])
    assert "relabel_rules_bundle" in relabeled
    assert "relabel_status" in relabeled
    assert "relabel_candidate_map" in relabeled
