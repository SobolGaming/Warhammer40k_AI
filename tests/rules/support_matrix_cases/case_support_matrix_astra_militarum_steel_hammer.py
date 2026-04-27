import os


def test_ceaseless_cannonade_detachment_ability_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000010786"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "engagement range" in notes_l
    assert "character" in notes_l


def test_accuracy_under_pressure_stratagem_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010788007"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Steel Hammer",
        stratagem_id=row.get("id", ""),
    )

    assert canonical_name == "ACCURACY UNDER PRESSURE"
    assert status in {"Implemented", "Supported"}
    notes_l = str(notes or "").lower()
    assert "astra militarum" in notes_l
    assert "re-roll hit rolls" in notes_l
    assert "end of phase" in notes_l


def test_adamantine_behemoth_stratagem_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010788004"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Steel Hammer",
        stratagem_id=row.get("id", ""),
    )

    assert canonical_name == "ADAMANTINE BEHEMOTH"
    assert status in {"Implemented", "Supported"}
    notes_l = str(notes or "").lower()
    assert "vehicle" in notes_l
    assert "move horizontally through terrain" in notes_l
    assert "end of phase" in notes_l
