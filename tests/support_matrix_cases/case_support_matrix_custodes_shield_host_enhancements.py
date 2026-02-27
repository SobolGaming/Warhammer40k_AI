import os


def test_custodes_shield_host_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008395002": "Auric Mantle",
        "000008395003": "Castellan's Mark",
        "000008395004": "From the Hall of Armouries",
        "000008395005": "Panoptispex",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
        )
        actual_name = str(row.get("name", "") or "").strip().replace("’", "'")
        expected_name = str(enhancement_name).strip().replace("’", "'")
        assert actual_name == expected_name

        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(enhancement_name).split()[0].lower() in str(notes or "").lower()
