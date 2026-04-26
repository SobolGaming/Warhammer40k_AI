from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_llm_agent_dataset.py"
    spec = importlib.util.spec_from_file_location("build_llm_agent_dataset_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load build_llm_agent_dataset.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_llm_agent_dataset_cli_writes_jsonl(monkeypatch, tmp_path: Path) -> None:
    mod = _load_script_module()
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "examples.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "decision_id": "d1",
                        "decision_type": "DECLARE_SHOTS",
                        "chosen_action_id": "a",
                        "candidates": [{"action_id": "a"}],
                        "mask": [True],
                    },
                    {
                        "decision_id": "d2",
                        "decision_type": "DECLARE_SHOTS",
                        "candidates": [{"action_id": "b"}],
                        "mask": [True],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_llm_agent_dataset.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert mod.main() == 0

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["decision_id"] == "d1"

