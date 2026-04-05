from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_victrix_honour_guard_glory_of_ultramar_support_matrix_case():
    description = (
        "In your opponent's Shooting phase, each time an enemy unit has shot, if any models from this unit were "
        "destroyed as a result of those attacks, this unit can make a Surge move. To do so, roll one D6: models "
        "in this unit move a number of inches up to the result, but this unit must end that move as close as "
        "possible to the closest enemy unit (excluding AIRCRAFT). When doing so, those models can be moved within "
        "Engagement Range of that enemy unit. This unit cannot make a Surge move while it is Battle-shocked or "
        "within Engagement Range of one or more enemy units, and can only make one Surge move per phase."
    )

    status, notes = _classify_ability(
        "Glory of Ultramar",
        description,
        faction_id="SM",
        datasheet_id="000004185",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "opponent shooting phase" in notes_l
    assert "surge move" in notes_l
    assert "engagement range" in notes_l


def test_space_marines_batch23_victrix_honour_guard_banner_of_macragge_support_matrix_case():
    description = (
        "Once per battle, at the start of the Fight phase, the bearer can use this ability. If it does, until the "
        "end of the phase, add 1 to the Strength and Attacks characteristics of melee weapons equipped by models in "
        "the bearer's unit."
    )

    status, notes = _classify_ability(
        "Banner of Macragge",
        description,
        faction_id="SM",
        datasheet_id="000004185",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "fight phase" in notes_l
    assert "attacks" in notes_l
    assert "strength" in notes_l
    assert "bearer's unit" in notes_l
