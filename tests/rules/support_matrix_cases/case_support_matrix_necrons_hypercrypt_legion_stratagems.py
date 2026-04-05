import os


def test_necrons_hypercrypt_legion_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000008555002": "wholly within 6",
        "000008555003": "4+ invulnerable save",
        "000008555004": "reanimation protocols for each friendly necrons unit currently in reserves",
        "000008555005": "implemented in engine",
        "000008555006": "can declare a charge this phase",
        "000008555007": "hazardous",
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
