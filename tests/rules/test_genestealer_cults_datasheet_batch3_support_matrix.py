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


def test_brood_surge_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Brood Surge",
        (
            "Each time an enemy unit is selected to shoot, after that unit has shot, if any models from this unit were destroyed as a result of those attacks, "
            "this unit can make a Brood Surge move. To do so, roll one D6: this unit can be moved a number of inches up to the result, but it must end that move "
            "as close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that enemy unit. "
            "If, at the start of the battle, no model in this unit is equipped with a hand flamer, each time this unit makes a Brood Surge move, it can be moved up to 6\" "
            "instead of up to D6\". A unit cannot make a Brood Surge move while it is Battle-shocked."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001571",
    )
    assert status == "Supported"
    assert "reactive move" in str(notes or "").lower()
    assert "closest non-aircraft enemy unit" in str(notes or "").lower()
    assert "hand flamer" in str(notes or "").lower()


def test_priority_target_support_matrix_classifies_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Priority Target",
        (
            "In your Shooting phase, after this model's unit has shot, select one enemy unit hit by one or more of those attacks made with a cult sniper rifle. "
            "Until the end of the phase, each time a friendly GENESTEALER CULTS model makes an attack that targets that enemy unit, re-roll a Hit roll of 1."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001565",
    )
    assert status == "Supported"
    assert "cult sniper rifle" in str(notes or "").lower()
    assert "genestealer cults" in str(notes or "").lower()


def test_heroic_fusillade_support_matrix_classifies_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Heroic Fusillade",
        (
            "Once per turn, after one model from your army with this ability has shot, you can select one INFANTRY unit hit by one or more of those attacks. "
            "That unit must take a Battle-shock test."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001566",
    )
    assert status == "Supported"
    assert "once per turn" in str(notes or "").lower()
    assert "infantry" in str(notes or "").lower()


def test_hypersensory_abilities_support_matrix_classifies_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Hypersensory Abilities",
        (
            "Once per turn, in your opponent's Movement phase, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this model, "
            "if this model is not within Engagement Range of one or more enemy units, it can shoot at that unit as if it were your Shooting phase and then "
            "make a Normal move of up to D6\" (it cannot embark within a TRANSPORT as part of this move)."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000001566",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "reactive shooting" in lowered
    assert "d6 reactive" in lowered
