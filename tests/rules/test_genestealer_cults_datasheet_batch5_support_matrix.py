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


def test_magus_mind_control_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Mind Control (Psychic)",
        (
            "At the start of your opponent's Shooting phase, one Psyker model from your army with this ability can use it. "
            "If used, select one enemy unit within 18\" of that PSYKER model and roll one D6: on a 1, that PSYKER model suffers D3 mortal wounds; "
            "on a 2-5, until the end of the phase, each time a model in that enemy unit makes an attack, subtract 1 from the Hit roll; "
            "on a 6, each time a model in that enemy unit makes an attack, subtract 1 from the Hit roll and subtract 1 from the Wound roll."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000000508",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "opponent shooting phase" in lowered
    assert "-1 to hit" in lowered
    assert "-1 to wound" in lowered


def test_magus_psychic_familiar_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Psychic Familiar",
        (
            "Once per battle, at the start of your opponent's Shooting phase, this model can use its psychic familiar. "
            "If it does, until the end of the phase, add 6\" to the range of its Mind Control ability."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000000508",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "once per battle" in lowered
    assert "mind control range" in lowered or "extend mind control range" in lowered
