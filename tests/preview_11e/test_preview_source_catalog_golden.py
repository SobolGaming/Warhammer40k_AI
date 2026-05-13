from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest


pytestmark = pytest.mark.preview


CATALOG_PATH = Path("docs/preview_sources/11e_faction_focus_may2026.json")


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_preview_source_catalog_records_only_preview_sources() -> None:
    catalog = _load_catalog()
    entries = catalog["entries"]

    assert catalog["catalog_id"] == "preview_sources:11e_faction_focus_may2026"
    assert catalog["preview_only"] is True
    assert catalog["rules_status"] == "preview_assumptions_only"
    assert len(entries) >= 6
    assert len({entry["source_id"] for entry in entries}) == len(entries)
    for entry in entries:
        parsed = urlparse(entry["url"])
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.warhammer-community.com"
        assert entry["published_at"].startswith("2026-05-")
        assert entry["preview_only"] is True
        assert entry["mechanics_observed"]


def test_preview_source_catalog_covers_required_generic_mechanics() -> None:
    catalog = _load_catalog()
    mechanics = {
        mechanic
        for entry in catalog["entries"]
        for mechanic in entry["mechanics_observed"]
    }

    assert "detection_marker" in mechanics
    assert "hidden_preserving_shooting" in mechanics
    assert "attack_scoped_detection_range_delta" in mechanics
    assert "cleave" in mechanics
    assert "updated_heavy" in mechanics
    assert "mobile" in mechanics
    assert "reactive_move" in mechanics
    assert "reactive_reserve_exit" in mechanics
    assert "heroic_intervention_modes" in mechanics
    assert "must_fight_next" in mechanics
    assert "upgrade_assignment" in mechanics


def test_preview_source_catalog_lists_generic_golden_tests() -> None:
    catalog = _load_catalog()
    golden_tests = tuple(catalog["generic_golden_tests"])

    assert "tests/preview_11e/test_keyword_cleave_golden.py" in golden_tests
    assert "tests/preview_11e/test_detection_marker_golden.py" in golden_tests
    assert "tests/preview_11e/test_hidden_preserving_shooting_golden.py" in golden_tests
    assert "tests/preview_11e/test_heroic_intervention_modes_golden.py" in golden_tests
    assert "tests/preview_11e/test_reactive_movement_golden.py" in golden_tests
    assert "tests/preview_11e/test_upgrade_assignment_golden.py" in golden_tests
    for golden_test in golden_tests:
        assert Path(golden_test).exists()


def test_preview_source_catalog_has_pr_015_confirmation_checklist() -> None:
    catalog = _load_catalog()
    checklist = catalog["pr_015_assumption_checklist"]
    mechanics = {item["mechanic"] for item in checklist}

    assert "detection_marker" in mechanics
    assert "cleave" in mechanics
    assert "upgrade_assignment" in mechanics
    assert "heroic_intervention_modes" in mechanics
    assert "battle_shock_persistence" in mechanics
    for item in checklist:
        assert item["release_day_action"].startswith("Confirm ")
