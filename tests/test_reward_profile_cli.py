from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _record(*, actor: str | None, active_player_id: str, p1_score: int, p2_score: int) -> dict:
    immediate = {}
    if actor is not None:
        immediate["actor_player_id"] = actor
    return {
        "game_id": "game-1",
        "omniscient_state": {
            "active_player_id": active_player_id,
            "players": [
                {"player_id": "p1", "score": int(p1_score)},
                {"player_id": "p2", "score": int(p2_score)},
            ],
        },
        "outcome": {
            "immediate_deltas": immediate,
            "end_of_turn_return": 0.0,
        },
    }


def test_annotate_decision_rewards_cli_writes_annotated_records(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "records_annotated.json"
    records = [
        _record(actor="p1", active_player_id="p1", p1_score=0, p2_score=0),
        _record(actor="p1", active_player_id="p1", p1_score=5, p2_score=0),
    ]
    input_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    script_path = repo_root / "scripts" / "annotate_decision_rewards.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--reward-profile",
        "dense_vp_delta_v1",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0
    annotated = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(annotated) == 2
    assert float(annotated[1]["outcome"]["end_of_turn_return"]) == 0.5
    assert float(annotated[0]["outcome"]["end_of_game_return"]) == 5.0
