def test_support_matrix_classifies_tau_precise_targeting_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "Each time a model in this unit makes an attack that targets a Spotted unit, you can re-roll the Hit roll."
    status, notes = gsm._classify_ability("Precise Targeting", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "spotted" in lowered
    assert "re-roll the hit roll" in lowered
