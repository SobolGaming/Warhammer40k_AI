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


def test_demolition_run_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Demolition Run",
        (
            "Once per turn, in your Movement phase, when this unit ends a Normal, Advance or Fall Back move, "
            "you can select one enemy unit within 6\" of and visible to this unit and roll one D6 for each ATALAN JACKALS "
            "model in this unit: for each 4+, that enemy unit suffers 1 mortal wound (to a maximum of 6 mortal wounds)."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="atalan-jackals",
    )
    assert status == "Supported"
    assert "visible enemy within 6" in str(notes or "").lower()
    assert "max 6" in str(notes or "").lower()


def test_outrider_gangs_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Outrider Gangs",
        (
            "Each time you use the Cult Ambush ability to set this unit back upon the battlefield, in addition to the normal rules, "
            "all of its models must be set up wholly within 9\" of a battlefield edge and at least one of its models must be touching "
            "one of your Cult Ambush markers (that marker is then removed from the battlefield). If this cannot be done, this unit "
            "cannot be set back up."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="atalan-jackals",
    )
    assert status == "Supported"
    assert "cult ambush setup" in str(notes or "").lower()
    assert "battlefield edge" in str(notes or "").lower()


def test_psionic_shield_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Psionic Shield (Psychic)",
        (
            "Once per battle, at the start of any phase, this model can use this ability. "
            "If it does, until the end of the phase, this model has a 4+ invulnerable save."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003715",
    )
    assert status == "Supported"
    assert "start of any phase" in str(notes or "").lower()
    assert "4+" in str(notes or "")


def test_biological_warfare_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Biological Warfare",
        (
            "Once per battle, when this model's unit is selected to fight, this model can use this ability. "
            "If it does, until the end of the phase, improve the Attacks and Damage characteristics of its injector goad by 3."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001572",
    )
    assert status == "Supported"
    assert "selected to fight" in str(notes or "").lower()
    assert "+3 Attacks" in str(notes or "")
    assert "injector goad" in str(notes or "").lower()


def test_alchemicus_familiar_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Alchemicus Familiar",
        (
            "Once per battle, when the bearer's unit is selected to fight, the bearer can use its alchemicus familiar. "
            "If it does, until the end of the phase, each time a model in the bearer's unit makes an attack that targets an INFANTRY unit, "
            "add 1 to the Wound roll. Designer's Note: Place an Alchemicus Familiar token next to the bearer, removing it once this ability has been used."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001572",
    )
    assert status == "Supported"
    assert "selected to fight" in str(notes or "").lower()
    assert "+1 to wound" in str(notes or "").lower()
    assert "infantry" in str(notes or "").lower()


def test_voice_of_new_truths_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Voice of New Truths",
        (
            "In your Command phase, one model from your army with this ability can use it. "
            "If it does, select one enemy unit within 18\" of it; that enemy unit must take a Battle-shock test."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001567",
    )
    assert status == "Supported"
    assert "command phase" in str(notes or "").lower()
    assert "18" in str(notes or "")
    assert "battle-shock" in str(notes or "").lower()


def test_grinding_clearance_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Grinding Clearance",
        (
            "Each time an enemy unit (excluding MONSTERS and VEHICLES) that is within Engagement Range of this model Falls Back, "
            "all models in that enemy unit must take a Desperate Escape test. When doing so, if that enemy unit is Battle-shocked, "
            "subtract 1 from each of those tests."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000000521",
    )
    assert status == "Supported"
    assert "desperate escape" in str(notes or "").lower()
    assert "non-monster/vehicle" in str(notes or "").lower()
    assert "-1" in str(notes or "")
