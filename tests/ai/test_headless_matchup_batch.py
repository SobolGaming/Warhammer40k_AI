from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_headless_matchup_batch.py"
    spec = importlib.util.spec_from_file_location("run_headless_matchup_batch_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_headless_matchup_batch.py for testing.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_args_defaults_to_rules_bounded_phase_cap(monkeypatch) -> None:
    mod = _load_script_module()
    monkeypatch.setattr(sys, "argv", ["run_headless_matchup_batch.py"])

    args = mod._parse_args()

    assert args.max_phase_steps == 50


def test_army_specs_are_deterministic_and_cover_requested_count() -> None:
    mod = _load_script_module()

    first = mod._army_specs(army_count=6, base_seed=123, factions=("Aeldari", "Orks", "Necrons"))
    second = mod._army_specs(army_count=6, base_seed=123, factions=("Aeldari", "Orks", "Necrons"))

    assert first == second
    assert len(first) == 6
    assert all(spec.seed > 123 for spec in first)
    assert {spec.faction for spec in first[:3]} == {"Aeldari", "Orks", "Necrons"}


def test_army_specs_anchor_faction_pairs_random_non_anchor_opponents() -> None:
    mod = _load_script_module()

    first = mod._army_specs(
        army_count=10,
        base_seed=321,
        factions=("Chaos Space Marines", "Aeldari", "Orks", "Necrons"),
        anchor_faction="Chaos Space Marines",
    )
    second = mod._army_specs(
        army_count=10,
        base_seed=321,
        factions=("Chaos Space Marines", "Aeldari", "Orks", "Necrons"),
        anchor_faction="Chaos Space Marines",
    )

    assert first == second
    assert [spec.faction for spec in first[0::2]] == ["Chaos Space Marines"] * 5
    assert set(spec.faction for spec in first[1::2]) <= {"Aeldari", "Orks", "Necrons"}
    assert all(spec.seed > 321 for spec in first)


def test_army_specs_anchor_faction_requires_opponent_pool() -> None:
    mod = _load_script_module()

    with pytest.raises(ValueError, match="non-anchor opponent"):
        mod._army_specs(
            army_count=2,
            base_seed=321,
            factions=("Chaos Space Marines",),
            anchor_faction="Chaos Space Marines",
        )


def test_write_summary_records_match_stats_and_bug_candidates(tmp_path: Path) -> None:
    mod = _load_script_module()
    paths = mod._batch_paths(tmp_path / "batch")
    armies = [
        {
            "army_index": 1,
            "faction": "Aeldari",
            "detachment": "Warhost",
            "points": 2000,
            "random_seed": 1,
            "style_tags": ["fast"],
            "army_list_path": "army1.txt",
        },
        {
            "army_index": 2,
            "faction": "Orks",
            "detachment": "War Horde",
            "points": 2000,
            "random_seed": 2,
            "style_tags": ["melee"],
            "army_list_path": "army2.txt",
        },
    ]
    matches = [
        {
            "match_index": 1,
            "player1": "Aeldari / Warhost",
            "player2": "Orks / War Horde",
            "status": "completed",
            "winner": "army1",
            "score": "<SCORE: 50 vs 40>",
            "decision_record_count": 12,
            "phase_steps": 5,
            "elapsed_seconds": 1.25,
            "tool_probe_diagnostic_counts": {},
            "reserve_arrival_diagnostic_counts": {},
            "stderr_error_counts": {},
            "stderr_warning_counts": {"WARNING sample": 1},
        }
    ]

    mod._write_summary(paths=paths, armies=armies, matches=matches, bugs=[], base_seed=99)

    assert paths.summary.exists()
    assert paths.stats.exists()
    text = paths.stats.read_text(encoding="utf-8")
    assert "Armies generated: 2 exact 2000-point rosters" in text
    assert "Aeldari / Warhost" in text
    assert "Stderr warning lines" in text


def test_expected_reserve_cutoff_warning_is_not_a_bug_candidate() -> None:
    mod = _load_script_module()

    bugs = mod._bug_candidates_from_match(
        {
            "match_index": 7,
            "player1": "Adeptus Mechanicus / Cohort Cybernetica",
            "player2": "Thousand Sons / Warpforged Cabal",
            "status": "completed",
            "tool_probe_diagnostic_counts": {},
            "reserve_arrival_diagnostic_counts": {"WARNING:reserve_destroyed_round3": 1},
            "stderr_error_counts": {},
        }
    )

    assert bugs == []


def test_unexpected_reserve_diagnostic_is_a_bug_candidate() -> None:
    mod = _load_script_module()

    bugs = mod._bug_candidates_from_match(
        {
            "match_index": 8,
            "player1": "Adeptus Mechanicus / Cohort Cybernetica",
            "player2": "Thousand Sons / Warpforged Cabal",
            "status": "completed",
            "tool_probe_diagnostic_counts": {},
            "reserve_arrival_diagnostic_counts": {
                "WARNING:reserve_destroyed_round3": 1,
                "WARNING:reserve_metadata_incomplete_post_deployment": 1,
            },
            "stderr_error_counts": {},
            "report_path": "report.json",
        }
    )

    assert len(bugs) == 1
    assert bugs[0]["bug_candidate"] == "Completed game emitted structured diagnostics."
    assert bugs[0]["reserve_arrival_diagnostic_counts"] == {
        "WARNING:reserve_metadata_incomplete_post_deployment": 1,
    }
