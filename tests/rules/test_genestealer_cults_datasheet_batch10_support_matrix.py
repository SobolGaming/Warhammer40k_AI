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


def test_reductus_saboteur_planted_explosives_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Planted Explosives",
        (
            "Once per battle, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this model, "
            "this model can use its Reductus mine. If it does, roll one D6: on a 2+, that enemy unit suffers D3+3 "
            "mortal wounds. Only one model from your army with this ability can use it in the same battle round."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000002525",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "battle-round" in lowered
    assert "d3+3" in lowered
