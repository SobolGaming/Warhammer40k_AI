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


def test_kult_of_speed_adrenaline_junkies_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000008871"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "speed freeks" in notes_l
    assert "shoot" in notes_l
    assert "charge" in notes_l
    assert "fell back" in notes_l
