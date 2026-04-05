import os


def test_windrider_host_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009903002": "Firstdrawn Blade",
        "000009903003": "Mirage Field",
        "000009903004": "Seersight Strike",
        "000009903005": "Echoes of Ulthanesh",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
            and str(item.get("name", "") or "").strip() == str(enhancement_name)
        )
        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(enhancement_name).split()[0].lower() in str(notes or "").lower()
