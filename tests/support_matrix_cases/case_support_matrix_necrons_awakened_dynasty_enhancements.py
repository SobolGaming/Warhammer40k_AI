import os


def test_necrons_awakened_dynasty_veil_of_darkness_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    enhancement_id = "000008372002"
    enhancement_name = "Veil of Darkness"

    row = next(
        item
        for item in enhancements
        if str(item.get("id", "") or "").strip() == enhancement_id
    )
    status, notes = gsm._enhancement_support(
        enhancement_name,
        enhancement_id,
        str(row.get("description", "") or ""),
    )
    assert status == "Supported"
    assert "deep strike" in str(notes or "").lower()
