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


def test_holy_piety_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Holy Piety",
        "Each time this model makes a melee attack, unless this model's unit is Battle-shocked, you can re-roll the Hit roll.",
        ability_id="",
        faction_id="AM",
        datasheet_id="ministorum-priest",
    )
    assert status == "Supported"
    assert "battle-shocked" in str(notes or "").lower()


def test_thunderous_head_butt_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Thunderous Head-butt",
        (
            "Each time this model's unit is selected to fight, you can select one enemy unit within Engagement Range of this model "
            "and roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="nork-deddog",
    )
    assert status == "Supported"
    assert "engagement range" in str(notes or "").lower()


def test_point_blank_barrage_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Point-blank Barrage",
        (
            "Each time a model in this unit makes a ranged attack that targets the closest eligible target, improve the Armour "
            "Penetration characteristic of that attack by 1."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="ogryn-squad",
    )
    assert status == "Supported"
    assert "closest eligible target" in str(notes or "").lower()


def test_psychic_barrier_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Psychic Barrier (Psychic)",
        (
            "At the start of your opponent's Shooting phase, you can roll one D6: on a 1, this PSYKER's unit suffers D3 mortal wounds; "
            "on a 2+, until the end of the phase, models in this PSYKER's unit have a 4+ invulnerable save."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="primaris-psyker",
    )
    assert status == "Supported"
    assert "opponent shooting phase" in str(notes or "").lower()


def test_ratling_battlemutt_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Ratling Battlemutt",
        (
            "Once per battle, when this unit is selected to shoot, it can use this ability. If it does, until the end of the phase, "
            "ranged weapons equipped by models in this unit have the [LETHAL HITS] ability."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="ratlings",
    )
    assert status == "Supported"
    assert "lethal hits" in str(notes or "").lower()


def test_shoot_sharp_and_scarper_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Shoot Sharp and Scarper",
        (
            "In your Shooting phase, after this unit has shot, if it is not within Engagement Range of any enemy units, it can make "
            "a Normal move as if it were your Movement phase. If it does, until the end of the turn, this unit is not eligible to declare a charge."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="ratlings",
    )
    assert status == "Supported"
    assert "move characteristic" in str(notes or "").lower() or "normal move" in str(notes or "").lower()
