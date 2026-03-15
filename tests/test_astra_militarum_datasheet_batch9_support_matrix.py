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


def test_daring_recon_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Daring Recon",
        (
            "At the start of your Shooting phase, select one enemy unit within 18\" of and visible to this unit. "
            "Until the end of the phase, each time a friendly ASTRA MILITARUM model makes an attack that targets that unit, "
            "re-roll a Hit roll of 1."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="scout-sentinels",
    )
    assert status == "Supported"
    assert "start of shooting phase" in str(notes or "").lower()
    assert "astra militarum" in str(notes or "").lower()


def test_titan_killer_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Titan-killer",
        (
            "Each time this model makes a ranged attack with its volcano cannon that targets a MONSTER or VEHICLE unit, "
            "that attack has the [DEVASTATING WOUNDS] ability."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="shadowsword",
    )
    assert status == "Supported"
    assert "volcano cannon" in str(notes or "").lower()
    assert "devastating wounds" in str(notes or "").lower()


def test_one_man_army_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "One-man Army",
        (
            "Once per turn, in your opponent's Shooting phase, when an enemy unit makes a ranged attack that targets a friendly "
            "Regiment unit within 3\" of this model, after that enemy unit has shot, this model can shoot as if it were your Shooting phase, "
            "but it must target only that enemy unit when doing so, and can only do so if that enemy unit is an eligible target."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="sly-marbo",
    )
    assert status == "Supported"
    assert "reactive shooting" in str(notes or "").lower()
    assert "opponent's shooting phase" in str(notes or "").lower()


def test_like_fighting_a_shadow_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Like Fighting a Shadow",
        (
            "In your Shooting phase, after this model has shot, if it is not within Engagement Range of one or more enemy units, "
            "it can make a Normal move. If it does, until the end of the turn, this model is not eligible to declare a charge."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="sly-marbo",
    )
    assert status == "Supported"
    assert "normal move" in str(notes or "").lower()


def test_mount_up_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Mount Up!",
        (
            "At the end of your opponent's Movement phase, if there are no models currently embarked within this TRANSPORT, "
            "you can select one friendly Astra Militarum Infantry unit (excluding Artillery units) that is wholly within 6\" of this TRANSPORT. "
            "Unless that unit is within Engagement Range of one or more enemy units, it can embark within this TRANSPORT."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="stormlord",
    )
    assert status == "Supported"
    assert "opponent movement phase" in str(notes or "").lower()
    assert "artillery" in str(notes or "").lower()


def test_concussive_wave_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Concussive Wave",
        (
            "In your Shooting phase, just after selecting a target for this model's Stormsword siege cannon, roll one D6 for the target unit "
            "and every other unit within 3\" of that unit: on a 5+, the unit being rolled for is struck by a concussive wave. After this model "
            "has finished making its attacks against that target unit this phase, each unit struck by a concussive wave suffers D3 mortal wounds."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="stormsword",
    )
    assert status == "Supported"
    assert "nearby units within 3" in str(notes or "").lower()
    assert "mortal wounds" in str(notes or "").lower()
