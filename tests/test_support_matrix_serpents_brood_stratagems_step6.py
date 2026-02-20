import os


def test_serpents_brood_step6_stratagem_is_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    stratagem_id = "000010650003"
    note_anchor = "normal move up to 6"

    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == stratagem_id
    )
    status, notes, _ = gsm._stratagem_support(
        str(row.get("name", "") or ""),
        str(row.get("description", "") or ""),
        detachment_name=str(row.get("detachment", "") or ""),
        stratagem_id=stratagem_id,
    )
    assert status == "Implemented"
    assert str(note_anchor).lower() in str(notes or "").lower()
