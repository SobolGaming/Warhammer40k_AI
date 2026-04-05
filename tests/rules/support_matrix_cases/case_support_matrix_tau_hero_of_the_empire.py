def test_support_matrix_classifies_tau_hero_of_the_empire_aura_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While a friendly T'AU EMPIRE unit is within 6\" of this model, "
        "each time a model in that unit makes a ranged attack, re-roll a Hit roll of 1."
    )
    status, notes = gsm._classify_ability("Hero of the Empire (Aura)", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "re-roll hit rolls of 1" in lowered
    assert "ranged attacks" in lowered
    assert "within 6" in lowered
