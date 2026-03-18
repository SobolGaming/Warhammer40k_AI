from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_wulfen_dreadnought_bestial_rage_support_matrix_case():
    description = (
        "Each time an enemy unit is selected to shoot, after that unit has shot, if this model lost one or more wounds "
        "as a result of those attacks, this model can make a Bestial Rage move. To do so, roll one D6, adding 2 to "
        "the result: this model can be moved a number of inches up to the result, but must finish that move as close "
        "as possible to the closest enemy unit (excluding AIRCRAFT), When doing so, this model can be moved within "
        "Engagement Range of that enemy unit. Each model can only make one Bestial Rage move per phase."
    )

    status, notes = _classify_ability(
        "Bestial Rage",
        description,
        faction_id="SM",
        datasheet_id="000004133",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "d6+2" in notes_l
    assert "non-aircraft" in notes_l
    assert "engagement range" in notes_l


def test_space_marines_batch23_wulfen_dreadnought_violent_fury_support_matrix_case():
    description = "If this model is equipped with two melee weapons, those weapon profiles have the [TWIN-LINKED] ability."

    status, notes = _classify_ability(
        "Violent Fury",
        description,
        faction_id="SM",
        datasheet_id="000004133",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "two melee weapons" in notes_l
    assert "twin-linked" in notes_l
