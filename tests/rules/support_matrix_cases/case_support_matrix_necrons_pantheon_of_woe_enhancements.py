import os


def test_necrons_pantheon_of_woe_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000010672002": "increasing the cp cost",
        "000010672003": "charge in turns it advanced",
        "000010672004": "-1 to hit",
        "000010672005": "more than 6",
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
