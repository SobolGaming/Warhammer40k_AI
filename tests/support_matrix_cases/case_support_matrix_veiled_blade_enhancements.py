import os


def test_veiled_blade_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009757002": "Decoy Targets",
        "000009757003": "Esoteric Explosives",
        "000009757004": "Intraneural Biotech",
        "000009757005": "Micromelta Rounds",
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
