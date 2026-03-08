def test_support_matrix_classifies_tyranids_death_scream_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Shooting phase, after this model has shot, select one unit hit by one or more of those attacks. "
        "That unit must take a Battle-shock test, subtracting 1 from that test."
    )
    status, notes = gsm._classify_ability("Death Scream", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "battle-shock" in notes_l
    assert "-1" in notes_l
