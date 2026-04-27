import os


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm, detachment_abilities


def test_blitz_brigade_eager_for_the_fight_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000010798"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "blitz brigade" in notes_l
    assert "disembarks" in notes_l
    assert "advance" in notes_l
    assert "charge" in notes_l


def test_blitz_brigade_armoured_duellists_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010800005"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Blitz Brigade",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "ARMOURED DUELLISTS"
    notes_l = str(notes or "").lower()
    assert "+1 to hit" in notes_l
    assert "+1 to wound" in notes_l
    assert "monster" in notes_l
    assert "vehicle" in notes_l


def test_blitz_brigade_impervious_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010800006"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Blitz Brigade",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "IMPERVIOUS"
    notes_l = str(notes or "").lower()
    assert "battlewagon" in notes_l
    assert "wound" in notes_l
    assert "strength" in notes_l
    assert "toughness" in notes_l
