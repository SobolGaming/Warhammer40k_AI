from __future__ import annotations

import json

import pytest

from warhammer40k_ai.waha_helper import WahaDataError, WahaHelper


def _write_minimal_waha_dir(path, *, overrides: dict[str, object] | None = None):
    payloads: dict[str, object] = {
        "Abilities.json": [],
        "Stratagems.json": [],
        "Enhancements.json": [],
        "Source.json": [],
        "Factions.json": [],
        "Detachment_abilities.json": [],
        "Datasheets_leader.json": [],
        "Datasheets_enhancements.json": [],
        "Datasheets.json": [
            {
                "id": "unit-1",
                "name": "Strict Test Unit",
                "source_id": "",
            }
        ],
    }
    payloads.update(dict(overrides or {}))
    path.mkdir()
    for filename, payload in payloads.items():
        (path / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_waha_helper_raises_for_missing_data_directory(tmp_path):
    with pytest.raises(WahaDataError, match="directory"):
        WahaHelper(data_dir=str(tmp_path / "missing"))


def test_waha_helper_raises_for_missing_mandatory_json(tmp_path):
    data_dir = tmp_path / "waha"
    _write_minimal_waha_dir(data_dir)
    (data_dir / "Datasheets.json").unlink()

    with pytest.raises(WahaDataError, match="Mandatory"):
        WahaHelper(data_dir=str(data_dir))


def test_waha_helper_raises_for_malformed_rows(tmp_path):
    data_dir = tmp_path / "waha"
    _write_minimal_waha_dir(data_dir, overrides={"Abilities.json": [{"name": "Missing id"}]})

    with pytest.raises(WahaDataError, match="missing required"):
        WahaHelper(data_dir=str(data_dir))
