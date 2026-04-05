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


def test_gc_line_breaker_support_matrix_classifies_supported():
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
        faction_id="GC",
        datasheet_id="000003980",
    )
    assert status == "Supported"
    assert "Demolisher" in str(notes or "")
    assert "Big Guns Never Tire" in str(notes or "")


def test_gc_urban_warfare_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Urban Warfare",
        (
            "Each time a ranged attack targets this model, if this model has the Benefit of Cover against that attack, "
            "subtract 1 from the Damage characteristic of that attack."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003981",
    )
    assert status == "Supported"
    assert "Benefit of Cover" in str(notes or "")
    assert "-1 Damage" in str(notes or "")


def test_gc_gung_ho_executioners_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Gung-ho Executioners",
        (
            "Each time this model makes an attack with its executioner plasma cannon that targets a unit that is Below "
            "Half-strength, add 1 to the Hit roll."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003982",
    )
    assert status == "Supported"
    assert "executioner plasma cannon" in str(notes or "").lower()
    assert "Below Half-strength" in str(notes or "")


def test_gc_mow_down_the_enemy_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Mow Down the Enemy",
        (
            "Each time this model makes an attack with its punisher gatling cannon that targets an enemy unit "
            "(excluding MONSTERS and VEHICLES), that attack has the [DEVASTATING WOUNDS] ability."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003984",
    )
    assert status == "Supported"
    assert "Punisher gatling cannon" in str(notes or "")
    assert "DEVASTATING WOUNDS" in str(notes or "")


def test_gc_pheromone_trail_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Pheromone Trail",
        "Once per battle round, you can target one model with this ability with the Rapid Ingress Stratagem for 0CP.",
        ability_id="",
        faction_id="GC",
        datasheet_id="000003883",
    )
    assert status == "Supported"
    assert "Rapid Ingress" in str(notes or "")
    assert "battle round" in str(notes or "").lower()
