import os


def test_necrons_autodivinator_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    row = next(
        item
        for item in enhancements
        if str(item.get("id", "") or "").strip() == "000008546004"
    )

    status, notes = gsm._enhancement_support(
        str(row.get("name", "") or ""),
        str(row.get("id", "") or ""),
        str(row.get("description", "") or ""),
    )

    assert status == "Supported"
    assert "opponent gains cp" in str(notes or "").lower()
