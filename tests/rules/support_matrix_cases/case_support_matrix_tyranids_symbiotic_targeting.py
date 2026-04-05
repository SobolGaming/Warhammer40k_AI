def test_support_matrix_classifies_tyranids_symbiotic_targeting_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
        "Until the end of the phase, each time a friendly TYRANIDS model makes an attack that targets that unit, "
        "re-roll a Hit roll of 1."
    )
    status, notes = gsm._classify_ability("Symbiotic Targeting", description, faction_id="TYR")

    assert status == "Supported"
    assert "re-roll hit rolls of 1" in notes.lower()
    assert "phase end" in notes.lower()
