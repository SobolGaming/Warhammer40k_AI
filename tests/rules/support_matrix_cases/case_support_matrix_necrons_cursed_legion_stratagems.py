import os


def test_necrons_cursed_legion_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010669003": "-1 to hit rolls",
        "000010669005": "eligible to shoot and declare a charge",
        "000010669002": "[sustained hits 1]",
        "000010669004": "reanimation protocols for d3 wounds",
        "000010669006": "adds 2 to charge rolls",
        "000010669007": "out-of-turn charge",
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
