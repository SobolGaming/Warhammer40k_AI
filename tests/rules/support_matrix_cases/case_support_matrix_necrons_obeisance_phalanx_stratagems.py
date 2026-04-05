import os


def test_necrons_obeisance_phalanx_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000008551002": "battle-shock and leadership",
        "000008551003": "critical hits on unmodified hit rolls of 5+",
        "000008551004": "-1 damage",
        "000008551005": "fights on death on a 4+",
        "000008551006": "precision",
        "000008551007": "objective control",
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
