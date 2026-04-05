import os


def test_tyranids_warrior_bioform_onslaught_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009737002": "Synaptic Tyrant",
        "000009737003": "Ocular Adaptation",
        "000009737004": "Sensory Assimilation",
        "000009737005": "Elevated Might",
    }

    for enhancement_id, enhancement_name in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == str(enhancement_id)
        )
        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert str(notes or "").strip()
