import os


def test_cosmic_distortion_detachment_ability_is_supported():
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
        if str(item.get("name", "") or "").strip() == "Cosmic Distortion"
        and str(item.get("detachment", "") or "").strip() == "Pantheon of Woe"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    assert "cosmic distortion" in str(notes or "").lower()


def test_cosmic_distortion_necrodermal_binding_restriction_is_supported():
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
        if str(item.get("name", "") or "").strip() == "Cosmic Distortion"
        and str(item.get("detachment", "") or "").strip() == "Pantheon of Woe"
    )
    restrictions = list(gsm._extract_restrictions(row.get("description", "") or ""))
    restriction = next(item for item in restrictions if "Necrodermal Binding" in str(item or ""))

    status, notes = gsm._classify_ability(
        restriction,
        "",
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    assert "necrodermal binding" in str(notes or "").lower()
