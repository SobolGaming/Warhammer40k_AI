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


def test_line_breaker_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Line-breaker",
        (
            "When making ranged attacks with its demolisher battle cannon, this model can target enemy units within "
            "Engagement Range of it (provided no other friendly units are also within Engagement Range of that enemy "
            "unit). In addition, when making ranged attacks, this model does not suffer the penalty to its Hit rolls "
            "for being within Engagement Range of one or more enemy units."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-demolisher",
    )
    assert status == "Supported"
    assert "Demolisher" in str(notes or "")
    assert "Big Guns Never Tire" in str(notes or "")


def test_urban_warfare_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Urban Warfare",
        (
            "Each time a ranged attack targets this model, if this model has the Benefit of Cover against that attack, "
            "subtract 1 from the Damage characteristic of that attack."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-eradicator",
    )
    assert status == "Supported"
    assert "Benefit of Cover" in str(notes or "")
    assert "-1 Damage" in str(notes or "")


def test_gung_ho_executioners_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Gung-ho Executioners",
        (
            "Each time this model makes an attack with its executioner plasma cannon that targets a unit that is Below "
            "Half-strength, add 1 to the Hit roll."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-executioner",
    )
    assert status == "Supported"
    assert "executioner plasma cannon" in str(notes or "").lower()
    assert "Below Half-strength" in str(notes or "")


def test_withering_hail_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Withering Hail",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those "
            "attacks made with its exterminator autocannon. Until the end of the phase, each time a friendly ASTRA "
            "MILITARUM unit makes an attack that targets that enemy unit, improve the Armour Penetration "
            "characteristic of that attack by 1. The same enemy unit can only be affected by this ability once per "
            "phase."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-exterminator",
    )
    assert status == "Supported"
    assert "exterminator autocannon" in str(notes or "").lower()
    assert "AP +1" in str(notes or "")


def test_mow_down_the_enemy_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Mow Down the Enemy",
        (
            "Each time this model makes an attack with its punisher gatling cannon that targets an enemy unit "
            "(excluding MONSTERS and VEHICLES), that attack has the [DEVASTATING WOUNDS] ability."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-punisher",
    )
    assert status == "Supported"
    assert "Punisher gatling cannon" in str(notes or "")
    assert "DEVASTATING WOUNDS" in str(notes or "")
