import os


def test_eradication_cohort_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    targeters_row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010748005"
    )
    assert str(targeters_row.get("detachment", "") or "") == "Eradication Cohort"
    assert "Damage roll" in str(targeters_row.get("description", "") or "")

    expected = {
        "000010748002": "lance",
        "000010748003": "falls back",
        "000010748004": "hazardous",
        "000010748005": "damage rolls",
        "000010748006": "mortal wound",
        "000010748007": "reactive shooting",
    }

    for stratagem_id, note_anchor in expected.items():
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
        assert status == "Implemented"
        assert str(note_anchor).lower() in str(notes or "").lower()
