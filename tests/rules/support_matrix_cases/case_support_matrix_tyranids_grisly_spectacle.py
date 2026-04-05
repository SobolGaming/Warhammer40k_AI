def test_support_matrix_classifies_tyranids_grisly_spectacle_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model is selected to fight, after resolving its attacks, if one or more enemy units were destroyed "
        "by those attacks, each enemy unit within 6\" of this model must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Grisly Spectacle", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "after this model fights" in notes_l
    assert "destroyed" in notes_l
    assert "within 6" in notes_l
