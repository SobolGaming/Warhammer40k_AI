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


def test_gc_primaris_psyker_psychic_barrier_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Psychic Barrier (Psychic)",
        (
            "At the start of your opponent's Shooting phase, you can roll one D6: on a 1, this PSYKER's unit suffers "
            "D3 mortal wounds; on a 2+, until the end of the phase, models in this PSYKER's unit have a 4+ invulnerable save."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003943",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "opponent shooting phase" in lowered
    assert "4+ invulnerable save" in lowered
