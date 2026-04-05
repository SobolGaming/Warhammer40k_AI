import os


def test_imperialis_fleet_fleetmaster_enhancement_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    row = next(
        item
        for item in enhancements
        if str(item.get("id", "") or "").strip() == "000009138005"
    )

    status, notes = gsm._enhancement_support(
        str(row.get("name", "") or ""),
        "000009138005",
        str(row.get("description", "") or ""),
    )
    assert status == "Supported"
    assert "fleetmaster" in str(notes or "").lower()
