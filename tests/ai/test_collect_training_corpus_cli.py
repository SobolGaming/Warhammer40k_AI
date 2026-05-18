from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_collect_training_corpus_cli_dry_run_lists_default_matchups(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "collect_training_corpus.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dry-run-matchups",
            "--target-accepted-games",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["target_accepted_games"] == 2
    assert payload["max_attempted_games"] == 4
    assert payload["workers"] == 5
    assert payload["matchups"]
    assert payload["matchups"][0]["player1_army"] == "army_lists/Aeldari_Warhost_2000.txt"
