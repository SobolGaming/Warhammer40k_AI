import os


def test_tyranids_synaptic_nexus_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008421002": "Power of the Hive Mind",
        "000008421003": "Psychostatic Disruption",
        "000008421004": "Synaptic Control",
        "000008421005": "The Dirgeheart of Kharis (Aura)",
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
