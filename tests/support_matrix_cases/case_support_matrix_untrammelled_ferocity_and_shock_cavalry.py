import os


def test_support_matrix_marks_untrammelled_ferocity_supported_and_shock_cavalry_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000008422005": ("Supported", "excluding titanic"),
        "000010270003": ("Implemented", "thunderwolf cavalry"),
    }

    for stratagem_id, (expected_status, note_anchor) in expected.items():
        row = next(
            item
            for item in stratagems
            if str(item.get("id", "") or "").strip() == str(stratagem_id)
        )
        status, notes, _ = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            detachment_name=str(row.get("detachment", "") or ""),
            stratagem_id=str(stratagem_id),
        )
        assert status == expected_status
        assert str(note_anchor).lower() in str(notes or "").lower()
