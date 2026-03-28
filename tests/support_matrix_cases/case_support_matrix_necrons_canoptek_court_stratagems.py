import os


def test_necrons_canoptek_court_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000008547006": "18",
        "000008547002": "canoptek models gain +1 to hit and +1 to wound",
        "000008547003": "devastating wounds",
        "000008547005": "reactive normal move up to 6",
        "000008547004": "ignores cover",
        "000008547007": "reanimation protocols for d3",
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
