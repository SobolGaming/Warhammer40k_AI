import os


def test_necrons_annihilation_legion_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008543002": "fight after the attacking unit finishes",
        "000008543003": "critical wound",
        "000008543005": "battle-shock",
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
