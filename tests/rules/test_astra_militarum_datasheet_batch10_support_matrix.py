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


def test_lord_castellan_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Lord Castellan",
        "While this model is leading a unit, that unit can be affected by up to two different Orders at the same time.",
        ability_id="",
        faction_id="AM",
        datasheet_id="ursula-creed",
    )
    assert status == "Supported"
    assert "two different Orders" in str(notes or "")


def test_omnissiahs_blessing_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Omnissiah's Blessing",
        (
            "In your Command phase, select one friendly Astra Militarum Vehicle model within 3\" of this model. "
            "That VEHICLE model regains up to D3 lost wounds and, until the start of your next Command phase, each "
            "time that VEHICLE model makes an attack, re-roll a Hit roll of 1."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="tech-priest-enginseer",
    )
    assert status == "Supported"
    assert "Hit rolls of 1" in str(notes or "")


def test_transport_support_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Transport Support",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of "
            "those attacks. Until the end of the phase, each time a model that disembarked from this TRANSPORT this "
            "turn makes an attack that targets that enemy unit, you can re-roll the Hit roll."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="taurox-prime",
    )
    assert status == "Supported"
    assert "re-roll Hit" in str(notes or "")


def test_airborne_insertion_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Airborne Insertion",
        "At the end of your opponent's Movement phase, one or more units embarked within this TRANSPORT can disembark from it.",
        ability_id="",
        faction_id="AM",
        datasheet_id="valkyrie",
    )
    assert status == "Supported"
    assert "disembark" in str(notes or "").lower()


def test_servo_sentry_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Servo-sentry",
        (
            "When this unit is set up on the battlefield using the Deep Strike ability, the Tempestor Aquilon can "
            "shoot with its sentry weapon (its sentry flamer, sentry grenade launcher or sentry hot-shot volley gun)."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="tempestus-aquilons",
    )
    assert status == "Supported"
    assert "Deep Strike" in str(notes or "")
