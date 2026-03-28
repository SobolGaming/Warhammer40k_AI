import os


def test_necrons_cryptek_conclave_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010665004": "re-roll hit rolls against it",
        "000010665003": "4+ invulnerable save if it is immortals",
        "000010665002": "ignores ballistic skill or weapon skill modifiers",
        "000010665007": "reanimation protocols for d3 wounds",
        "000010665005": "gains the cryptek keyword until end of phase",
        "000010665006": "additional technosorcerous augmentations ability",
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
