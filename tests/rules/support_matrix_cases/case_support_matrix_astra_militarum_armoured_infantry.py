import os


def test_squadron_command_detachment_ability_is_supported():
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
        if str(item.get("id", "") or "").strip() == "000010790"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "squadron" in notes_l
    assert "on my signal" in notes_l
    assert "armoured skirmisher" in notes_l


def test_burst_of_speed_stratagem_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010792004"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Armoured Infantry",
        stratagem_id=row.get("id", ""),
    )

    assert canonical_name == "BURST OF SPEED"
    assert status in {"Implemented", "Supported"}
    notes_l = str(notes or "").lower()
    assert "reactive normal move" in notes_l
    assert "d6" in notes_l
    assert "remain stationary" in notes_l
    assert "reserves" in notes_l


def test_combined_fire_stratagem_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010792006"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Armoured Infantry",
        stratagem_id=row.get("id", ""),
    )

    assert canonical_name == "COMBINED FIRE"
    assert status in {"Implemented", "Supported"}
    notes_l = str(notes or "").lower()
    assert "armoured skirmisher" in notes_l
    assert "benefit of cover" in notes_l
    assert "+2 strength" in notes_l


def test_mobile_firebase_stratagem_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010792003"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Armoured Infantry",
        stratagem_id=row.get("id", ""),
    )

    assert canonical_name == "MOBILE FIREBASE"
    assert status in {"Implemented", "Supported"}
    notes_l = str(notes or "").lower()
    assert "armoured skirmisher" in notes_l
    assert "advances or falls back" in notes_l
    assert "eligible to shoot" in notes_l
