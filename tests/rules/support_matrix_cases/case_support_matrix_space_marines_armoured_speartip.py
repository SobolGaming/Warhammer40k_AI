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


def test_armoured_speartip_rapid_deployment_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000010777"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "armoured speartip" in notes_l
    assert "disembark" in notes_l
    assert "d6" in notes_l
    assert "d3+3" in notes_l
    assert "heavy transport" in notes_l
