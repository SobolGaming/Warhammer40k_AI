def test_support_matrix_classifies_tau_pechra_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "Ranged weapons equipped by the bearer's unit have the [IGNORES COVER] ability."
    status, notes = gsm._classify_ability("Pech'ra", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "unit ranged weapons" in lowered
    assert "ignores cover" in lowered
