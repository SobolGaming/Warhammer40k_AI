import os


def test_the_lost_brethren_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000009186002": ("Sanguinius' Grace", "sanguinius"),
        "000009186003": ("Blood Shard", "blood shard"),
        "000009186004": ("To Slay the Warmaster", "warmaster"),
        "000009186005": ("Vengeful Onslaught", "vengeful"),
    }

    for enhancement_id, (enhancement_name, notes_fragment) in expected.items():
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
        assert str(notes_fragment or "").lower() in str(notes or "").lower()
