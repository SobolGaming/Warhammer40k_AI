def test_support_matrix_classifies_tyranids_psychic_terror_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "If one or more models from your army with this ability are on the battlefield when you unleash the Shadow in the Warp, "
        "subtract 1 from the Battle-shock test each enemy unit on the battlefield must take as a result."
    )
    status, notes = gsm._classify_ability("Psychic Terror (Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "shadow in the warp" in notes_l
    assert "-1" in notes_l
    assert "battle-shock" in notes_l
