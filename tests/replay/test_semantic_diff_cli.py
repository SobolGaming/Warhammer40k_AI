from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_semantic_diff_cli_outputs_training_scope() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "classify_semantic_diff.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--source-core-rules-id",
        "core_10e",
        "--source-rules-commentary-id",
        "commentary_a",
        "--source-mission-pack-id",
        "mission_a",
        "--source-terrain-pack-id",
        "terrain_a",
        "--source-dataslate-id",
        "dataslate_a",
        "--source-points-id",
        "points_a",
        "--source-faction-pack-id",
        "faction_a",
        "--source-detachment-pack-id",
        "detachment_a",
        "--target-core-rules-id",
        "core_10e",
        "--target-rules-commentary-id",
        "commentary_a",
        "--target-mission-pack-id",
        "mission_b",
        "--target-terrain-pack-id",
        "terrain_a",
        "--target-dataslate-id",
        "dataslate_a",
        "--target-points-id",
        "points_a",
        "--target-faction-pack-id",
        "faction_a",
        "--target-detachment-pack-id",
        "detachment_a",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )

    payload = json.loads(completed.stdout)
    assert payload["changed_bundle_fields"] == ["mission_pack_id"]
    assert payload["training_scope"]["scope_id"] == "scoring_surface_update"
