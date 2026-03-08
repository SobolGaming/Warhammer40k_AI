def test_support_matrix_classifies_tyranids_hypnotic_gaze_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the start of the Fight phase, select one enemy unit within Engagement Range of this model. "
        "Until the end of the phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
    )
    status, notes = gsm._classify_ability("Hypnotic Gaze (Psychic)", description, faction_id="TYR")

    assert status == "Supported"
    notes_l = notes.lower()
    assert "engagement range" in notes_l
    assert "hit" in notes_l
