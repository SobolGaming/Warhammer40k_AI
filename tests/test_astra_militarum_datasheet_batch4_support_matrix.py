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


def test_tanith_camo_cloaks_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Tanith Camo-cloaks",
        "Models in this unit have the Benefit of Cover.",
        ability_id="",
        faction_id="AM",
        datasheet_id="gaunts-ghosts",
    )
    assert status == "Supported"
    assert "Benefit of Cover" in str(notes or "")


def test_close_quarters_warfare_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Close-quarters Warfare",
        "This model does not suffer the penalty to its Hit rolls for making ranged attacks while enemy units are within Engagement Range of it.",
        ability_id="",
        faction_id="AM",
        datasheet_id="hellhammer",
    )
    assert status == "Supported"
    assert "Big Guns Never Tire" in str(notes or "")


def test_flush_them_out_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Flush Them Out",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of "
            "those attacks. Until the start of your next Shooting phase, that unit is scattered. While a unit is "
            "scattered, it cannot have the Benefit of Cover."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="hellhound",
    )
    assert status == "Supported"
    assert "Benefit of Cover" in str(notes or "")
    assert "next Shooting phase" in str(notes or "")


def test_melta_mine_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Melta Mine",
        (
            "Once per battle, at the start of any phase, you can select one enemy unit within 3\" of the bearer and "
            "roll one D6: on a 2+, that enemy unit suffers D3 mortal wounds, or 2D3 mortal wounds instead if it is "
            "a VEHICLE unit."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="kasrkin",
    )
    assert status == "Supported"
    assert "2D3" in str(notes or "")
    assert "VEHICLE" in str(notes or "")


def test_warrior_elite_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Warrior Elite",
        (
            "Once per battle round, at the start of any phase, you can select one Order to affect this unit until "
            "the start of your next Command phase, in addition to any other Orders issued to this unit by an Officer "
            "model this battle round."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="kasrkin",
    )
    assert status == "Supported"
    assert "additional Order" in str(notes or "")
