import os


def test_custodes_auric_champions_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008930002": "Blade Imperator",
        "000008930003": "Inspirational Exemplar",
        "000008930004": "Martial Philosopher",
        "000008930005": "Veiled Blade",
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
