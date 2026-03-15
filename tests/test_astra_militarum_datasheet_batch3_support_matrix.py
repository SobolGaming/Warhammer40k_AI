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


def test_death_korps_medi_pack_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Death Korps Medi-pack",
        (
            "At the start of your Command phase, if the bearer's unit is below its Starting Strength, you can return "
            "up to D3 destroyed Death Korps Troopers to this unit (if this unit contains two models equipped with a "
            "Death Korps medi-pack, return up to D3+1 destroyed Death Korps Troopers to this unit instead)."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="death-korps-of-krieg",
    )
    assert status == "Supported"
    assert "Starting Strength" in str(notes or "")
    assert "D3+1" in str(notes or "")


def test_close_range_titan_killer_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Close-range Titan Killer",
        (
            "Each time this model's magma cannon targets a MONSTER or VEHICLE unit, that target is always considered "
            "to be within half range of that weapon."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="doomhammer",
    )
    assert status == "Supported"
    assert "MAGMA CANNON" in str(notes or "")
    assert "MONSTER/VEHICLE" in str(notes or "")
