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


def test_primus_cult_demagogue_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Cult Demagogue",
        "While this model is leading a unit, each time a model in that unit makes an attack, you can add 1 to the Hit roll.",
        ability_id="",
        faction_id="GC",
        datasheet_id="000000509",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "+1 to hit" in lowered or "gain +1 to hit" in lowered


def test_primus_decoys_and_misdirection_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Decoys and Misdirection",
        (
            "If your army includes one or more models with this ability, after both players have deployed their armies, "
            "select up to three GENESTEALER CULTS units from your army and redeploy them. When doing so, you can set "
            "those units up in Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000000509",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "redeploy up to three" in lowered
    assert "strategic reserves" in lowered
