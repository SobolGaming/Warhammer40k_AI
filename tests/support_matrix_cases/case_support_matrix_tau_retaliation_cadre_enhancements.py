import os


def test_tau_retaliation_cadre_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000008815002": ("Internal Grenade Racks", "grenades"),
        "000008815003": ("Prototype Weapon System", "deterministic mode selection"),
        "000008815004": ("Puretide Engram Neurochip", "gain 1cp"),
        "000008815005": ("Starflare Ignition System", "starflare"),
    }

    for enhancement_id, (enhancement_name, note_fragment) in expected.items():
        row = next(
            item
            for item in enhancements
            if str(item.get("id", "") or "").strip() == enhancement_id
            and str(item.get("name", "") or "").strip().replace("\u2019", "'") == enhancement_name
        )
        status, notes = gsm._enhancement_support(
            enhancement_name,
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert note_fragment in str(notes or "").lower()
