import os


def test_freeblade_company_detachment_ability_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm._seed_ability_support_maps(abilities, detachment_abilities)

    description = (
        "Imperial Knights models from your army have the Feel No Pain 6+ ability. In addition, at the start of your "
        "Command phase, each Imperial Knights model from your army regains 1 lost wound."
    )

    status, notes = gsm._classify_ability(
        "Knights of Legend",
        description,
        ability_id="000010754",
        faction_id="QI",
    )

    assert status == "Supported"
    assert "feel no pain 6+" in str(notes or "").lower()
    assert "regains 1 lost wound" in str(notes or "").lower()


def test_freeblade_company_enhancements_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    expected = {
        "000010755002": "Bringer of Justice",
        "000010755003": "Hunter",
        "000010755004": "Mysterious Guardian",
        "000010755005": "Sanctuary",
    }

    for enhancement_id, note_fragment in expected.items():
        row = next(item for item in enhancements if str(item.get("id", "") or "").strip() == enhancement_id)
        status, notes = gsm._enhancement_support(
            str(row.get("name", "") or ""),
            enhancement_id,
            str(row.get("description", "") or ""),
        )
        assert status == "Supported"
        assert note_fragment.lower() in str(notes or "").lower()


def test_freeblade_company_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010756003": "re-rolls Hit rolls of 1",
        "000010756002": "Deadly Demise",
        "000010756006": "-1 to incoming Wound rolls",
        "000010756007": "Strategic Reserves",
        "000010756005": "Blast",
        "000010756004": "fixed Advance distance of 6",
    }

    for stratagem_id, note_fragment in expected.items():
        row = next(item for item in stratagems if str(item.get("id", "") or "").strip() == stratagem_id)
        status, notes, _ = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            detachment_name=str(row.get("detachment", "") or ""),
            stratagem_id=stratagem_id,
        )
        assert status == "Implemented"
        assert note_fragment.lower() in str(notes or "").lower()
