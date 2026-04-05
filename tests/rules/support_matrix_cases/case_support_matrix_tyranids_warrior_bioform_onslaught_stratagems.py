import os


def test_tyranids_warrior_bioform_onslaught_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "000009738002": "re-rolls wound rolls of 1",
        "000009738003": "+2 strength",
        "000009738004": "return 1 destroyed model",
        "000009738005": "sticky",
        "000009738006": "ignores cover",
        "000009738007": "subtract 1 from the wound roll",
    }
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    for stratagem_id, note_fragment in expected.items():
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
        assert note_fragment.lower() in str(notes or "").lower()
