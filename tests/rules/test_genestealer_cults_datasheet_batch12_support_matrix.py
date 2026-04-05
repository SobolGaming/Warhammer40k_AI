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


def test_gc_taurox_prime_transport_support_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Transport Support",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of "
            "those attacks. Until the end of the phase, each time a model that disembarked from this TRANSPORT this "
            "turn makes an attack that targets that enemy unit, you can re-roll the Hit roll."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="taurox-prime",
    )
    assert status == "Supported"
    assert "re-roll Hit" in str(notes or "")
