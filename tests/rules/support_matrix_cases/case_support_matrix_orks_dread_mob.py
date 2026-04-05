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


def test_dread_mob_try_dat_button_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000008875"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "hazardous" in notes_l
    assert "fail-on-2" in notes_l


def test_dread_mob_keywords_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000008876"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    assert "battleline" in str(notes or "").lower()


def test_dread_mob_conniving_runts_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000008878006"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "d3+1" in notes_l
    assert "normal move" in notes_l
