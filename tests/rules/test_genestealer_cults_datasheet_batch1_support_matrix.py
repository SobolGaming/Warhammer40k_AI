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


def test_the_chosen_one_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "The Chosen One",
        (
            "While this model is leading a unit, each time a model in that unit is destroyed by a melee attack, "
            "if that model has not fought this phase, roll one D6. On a 4+, do not remove the destroyed model "
            "from play; it can fight after the attacking model's unit has finished making its attacks, and is then removed from play."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="abominant",
    )
    assert status == "Supported"
    assert "4+" in str(notes or "")
    assert "fight" in str(notes or "").lower()


def test_claimed_for_the_cult_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Claimed for the Cult",
        (
            "At the start of your Command phase, roll one D6 for each objective marker you control that has one or more "
            "units from your army with this ability within range of it. If one or more of the results is a 4+, you gain 1CP."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="acolyte-hybrids-with-autopistols",
    )
    assert status == "Supported"
    assert "controlled objective" in str(notes or "").lower()
    assert "1 cp" in str(notes or "").lower()


def test_industrialised_destruction_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Industrialised Destruction",
        (
            "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. "
            "If the target of that attack is an enemy unit within range of an objective marker, you can re-roll the Wound roll."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="acolyte-hybrids-with-hand-flamers",
    )
    assert status == "Supported"
    assert "objective marker" in str(notes or "").lower()
    assert "re-roll wound roll" in str(notes or "").lower()


def test_flare_launcher_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Flare Launcher",
        "The bearer's unit has the SMOKE keyword and you can target it with the Smokescreen Stratagem for 0CP.",
        ability_id="",
        faction_id="GC",
        datasheet_id="achilles-ridgerunners",
    )
    assert status == "Supported"
    assert "smoke keyword" in str(notes or "").lower()
    assert "0cp" in str(notes or "").lower()


def test_spotter_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Spotter",
        "The bearer's ranged weapons have a Ballistic Skill characteristic of 3+.",
        ability_id="",
        faction_id="GC",
        datasheet_id="achilles-ridgerunners",
    )
    assert status == "Supported"
    assert "bs 3+" in str(notes or "").lower()


def test_survey_augur_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Survey Augur",
        (
            "Each time the bearer's unit has shot, select one enemy unit that was hit by one or more attacks made by the bearer "
            "this phase. Until the end of the phase, each time a friendly GENESTEALER CULTS model makes an attack against that unit, "
            "that attack has the [IGNORES COVER] ability."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="achilles-ridgerunners",
    )
    assert status == "Supported"
    assert "ignores cover" in str(notes or "").lower()
    assert "genestealer cults" in str(notes or "").lower()


def test_summon_the_cult_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Summon the Cult",
        (
            "Once per battle, when you have to remove a Cult Ambush marker because your opponent has moved too close to it, "
            "if one or more models from your army with this ability are on the battlefield, you can use this ability. If you do, "
            "instead of removing that marker, you can place it anywhere on the battlefield that is within 12\" of a model from your "
            "army with this ability and more than 9\" horizontally away from all enemy units (if this is not possible, this ability is "
            "not considered to have been used and that marker is removed as normal)."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="acolyte-iconward",
    )
    assert status == "Supported"
    assert "cult ambush marker" in str(notes or "").lower()
    assert "pick_point" in str(notes or "").lower() or "optional relocation" in str(notes or "").lower()
