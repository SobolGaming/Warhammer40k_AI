def test_support_matrix_classifies_tyranids_neural_disruption_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Command phase, select one enemy unit within 12\" of this model. "
        "That unit must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Neural Disruption", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "command phase" in notes_l
    assert "battle-shock" in notes_l
    assert "within 12" in notes_l
