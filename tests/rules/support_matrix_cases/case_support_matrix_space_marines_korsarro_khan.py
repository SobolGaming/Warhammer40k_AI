def test_support_matrix_space_marines_korsarro_khan_for_the_khan():
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(
        "For the Khan!",
        (
            "While this model is leading a unit, ranged weapons equipped by models in that unit have the [ASSAULT] "
            "ability and melee weapons equipped by models in that unit have the [LANCE] ability."
        ),
        faction_id="SM",
        datasheet_id="000002709",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "assault" in notes_l
    assert "lance" in notes_l
