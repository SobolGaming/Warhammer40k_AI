import os


def test_necrons_obeisance_phalanx_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008550002": "loses 1cp",
        "000008550003": "anti-infantry 5+",
        "000008550004": "-1 to hit",
        "000008550005": "re-roll hit rolls",
    }

    for enhancement_id, phrase in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == enhancement_id
        )
        status, notes = gsm._enhancement_support(
            str(row.get("name", "") or ""),
            str(row.get("id", "") or ""),
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert phrase in str(notes or "").lower()
