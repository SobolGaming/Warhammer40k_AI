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


def test_gc_line_breaker_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Line-breaker",
        (
            "When making ranged attacks with its demolisher battle cannon, this model can target enemy units within "
            "Engagement Range of it (provided no other friendly units are also within Engagement Range of that enemy "
            "unit). In addition, when making ranged attacks, this model does not suffer the penalty to its Hit rolls "
            "for being within Engagement Range of one or more enemy units."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003980",
    )
    assert status == "Supported"
    assert "Demolisher" in str(notes or "")
    assert "Big Guns Never Tire" in str(notes or "")


def test_gc_urban_warfare_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Urban Warfare",
        (
            "Each time a ranged attack targets this model, if this model has the Benefit of Cover against that attack, "
            "subtract 1 from the Damage characteristic of that attack."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003981",
    )
    assert status == "Supported"
    assert "Benefit of Cover" in str(notes or "")
    assert "-1 Damage" in str(notes or "")
