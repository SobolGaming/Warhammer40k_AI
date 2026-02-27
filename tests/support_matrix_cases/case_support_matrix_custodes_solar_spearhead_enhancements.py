import os


def test_custodes_solar_spearhead_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009753004": "Honoured Fallen (Aura)",
        "000009753005": "Veteran of the Kataphraktoi",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
        )
        actual_name = str(row.get("name", "") or "").strip().replace("â€™", "'")
        expected_name = str(enhancement_name).strip().replace("â€™", "'")
        assert actual_name == expected_name

        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(enhancement_name).split()[0].lower() in str(notes or "").lower()

