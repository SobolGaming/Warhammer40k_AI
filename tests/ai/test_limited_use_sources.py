from __future__ import annotations

from pathlib import Path

from warhammer40k_ai.ml.limited_use_sources import summarize_limited_use_source_entries


def test_limited_use_source_scan_covers_requested_wahapedia_files() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    summary = summarize_limited_use_source_entries(repo_root=repo_root)

    by_file = summary["by_file"]
    assert by_file["wahapedia_data/Abilities.json"]["entry_count"] >= 6
    assert by_file["wahapedia_data/Datasheets_abilities.json"]["entry_count"] >= 448
    assert by_file["wahapedia_data/Detachment_abilities.json"]["entry_count"] >= 19
    assert by_file["wahapedia_data/Stratagems.json"]["entry_count"] >= 33
    assert by_file["wahapedia_data/Enhancements.json"]["entry_count"] >= 96
    assert summary["limited_use_entry_count"] > 0
    assert summary["scope_counts"]["battle"] > 0
    assert summary["scope_counts"]["battle_round"] > 0
    assert summary["scope_counts"]["turn"] > 0
    fire_overwatch = [
        entry
        for entry in list(summary.get("entries", []) or [])
        if entry.get("source_file") == "wahapedia_data/Stratagems.json"
        and str(entry.get("name", "") or "").upper() == "FIRE OVERWATCH"
    ]
    assert len(fire_overwatch) == 1
    assert fire_overwatch[0]["scopes"] == ["turn"]
