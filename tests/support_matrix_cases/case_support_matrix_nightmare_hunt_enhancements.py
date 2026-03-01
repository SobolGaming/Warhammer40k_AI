import os


def test_nightmare_hunt_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000010641002": "Greyveil Hex",
        "000010641003": "Warp-fuelled Thrusters",
        "000010641004": "Terrorglut Parasite",
        "000010641005": "Sorrowscent Vulture",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
            and str(item.get("name", "") or "").strip().replace("\u2019", "'") == str(enhancement_name)
        )
        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(enhancement_name).split()[0].lower() in str(notes or "").lower()
