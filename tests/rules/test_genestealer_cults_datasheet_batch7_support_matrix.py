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


def test_nexos_cult_infiltration_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Cult Infiltration",
        (
            "At the start of each player's Command phase, if this model is on the battlefield, you can select one of "
            "your Cult Ambush markers that is on the battlefield and has not been moved this turn and move it up to 6\"."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001571",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "command phase" in lowered
    assert "cult ambush marker" in lowered
    assert "up to 6" in lowered
