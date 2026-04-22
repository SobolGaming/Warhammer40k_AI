from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_main_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "main.py"
    spec = importlib.util.spec_from_file_location("main_script_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load main.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_parser_supports_profile_options(tmp_path) -> None:
    mod = _load_main_module()
    parser = mod._build_parser()

    args = parser.parse_args(
        [
            "--profile",
            "--profile-dir",
            str(tmp_path),
            "--profile-sort",
            "cumtime",
            "--profile-lines",
            "30",
            "--profile-label",
            "ui_baseline",
        ]
    )

    assert args.profile is True
    assert args.profile_dir == str(tmp_path)
    assert args.profile_sort == "cumtime"
    assert args.profile_lines == 30
    assert args.profile_label == "ui_baseline"
