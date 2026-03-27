import os


def test_necrons_cursed_legion_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000010668002": "models in the bearer's unit gain +2\" move",
        "000010668003": "attach to destroyer cult non-character units",
        "000010668004": "add 1 to the hit roll",
        "000010668005": "surge move up to d6",
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
