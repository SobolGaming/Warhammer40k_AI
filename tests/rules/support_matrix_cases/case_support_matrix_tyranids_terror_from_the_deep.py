def test_support_matrix_classifies_tyranids_terror_from_the_deep_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model is set up on the battlefield using the Deep Strike ability, "
        "roll one D6 for each enemy unit within 12\" of this model: on a 2-4, that unit suffers D3 mortal wounds; "
        "on a 5+, that unit suffers 3 mortal wounds and must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Terror From The Deep", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "deep strike" in notes_l
    assert "within 12" in notes_l
    assert "2-4" in notes_l
    assert "battle-shock" in notes_l
