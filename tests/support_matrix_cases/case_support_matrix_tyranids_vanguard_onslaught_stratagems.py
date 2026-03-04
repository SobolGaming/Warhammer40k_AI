import os


def test_tyranids_vanguard_onslaught_invisible_hunter_is_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000008418007"
    )
    status, notes, _ = gsm._stratagem_support(
        str(row.get("name", "") or ""),
        str(row.get("description", "") or ""),
        detachment_name=str(row.get("detachment", "") or ""),
        stratagem_id="000008418007",
    )
    assert status == "Implemented"
    assert "vanguard invader" in str(notes or "").lower()
