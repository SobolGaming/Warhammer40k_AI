def test_support_matrix_classifies_tau_rites_of_feasting_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this model is leading a unit, models in that unit have the Feel No Pain 6+ ability. "
        "If that unit destroys one or more enemy units in the Fight phase, until the end of the battle, "
        "models in that unit have the Feel No Pain 5+ ability instead."
    )
    status, notes = gsm._classify_ability("Rites of Feasting", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "feel no pain 6+" in lowered
    assert "feel no pain 5+" in lowered
    assert "fight phase" in lowered
