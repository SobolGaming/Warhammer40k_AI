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
    return gsm


def test_sanctus_creeping_shadow_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Creeping Shadow",
        (
            "If this model is equipped with a cult sniper rifle, once per turn, when an enemy unit ends a Normal, "
            "Advance or Fall Back move within 9\" of this model, if this model is not within Engagement Range of "
            "one or more enemy units, it can make a Normal move of up to 6\"."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001569",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "cult sniper rifle" in lowered
    assert "reactive normal move" in lowered
