import os


def test_blood_legion_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009815002": "Slaughterthirst (Aura)",
        "000009815003": "Fury's Cage",
        "000009815004": "Brazenmaw",
        "000009815005": "Gateway Unto Damnation",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
        )
        row_name = str(row.get("name", "") or "").strip().replace("\u2019", "'")
        assert row_name == str(enhancement_name)
        status, notes = gsm._enhancement_support(
            str(row.get("name", "") or ""),
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(enhancement_name).split()[0].lower() in str(notes or "").lower()
