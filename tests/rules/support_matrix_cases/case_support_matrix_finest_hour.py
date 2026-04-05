def test_support_matrix_classifies_finest_hour_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    gsm._seed_ability_support_maps([], [])

    description = (
        "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, until the "
        "end of the phase, add 3 to the Attacks characteristic of melee weapons equipped by this model and those "
        "weapons have the [DEVASTATING WOUNDS] ability."
    )

    status, notes = gsm._classify_ability(
        "Finest Hour",
        description,
        faction_id="SM",
        datasheet_id="000000073",
    )

    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "fight phase" in lowered
    assert "devastating wounds" in lowered
