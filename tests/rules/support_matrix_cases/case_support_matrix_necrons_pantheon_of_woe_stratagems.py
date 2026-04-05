import os


def test_necrons_pantheon_of_woe_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010673002": "deadly demise",
        "000010673003": "battle-shock test at -1",
        "000010673004": "reanimation protocols for d3 wounds",
        "000010673005": "re-rolls hit rolls of 1",
        "000010673006": "fights on death",
        "000010673007": "desperate escape tests",
    }

    for stratagem_id, phrase in expected.items():
        row = next(
            item
            for item in stratagems
            if str(item.get("id", "") or "").strip() == stratagem_id
        )
        status, notes, _name = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            stratagem_id=str(row.get("id", "") or ""),
        )
        assert status == "Implemented"
        assert phrase in str(notes or "").lower()
